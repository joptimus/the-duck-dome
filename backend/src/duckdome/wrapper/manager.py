"""Manages persistent interactive CLI processes for each agent.

Each agent gets:
- A subprocess.Popen process (Windows) or tmux session (Mac/Linux)
- A QueueWatcher thread that polls its queue file
- A MCP config file pointing to the DuckDome MCP server
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from duckdome.wrapper.console_monitor import ConsoleMonitor
from duckdome.wrapper.injector import inject
from duckdome.wrapper.mcp_config import generate_agent_token, generate_gemini_settings, generate_mcp_config
from duckdome.wrapper.mcp_proxy import McpProxy
from duckdome.wrapper.providers import build_launch_args
from duckdome.wrapper.queue import read_queue_entries

logger = logging.getLogger(__name__)


def _resolve_launch_cwd(cwd: str | None) -> str:
    """Resolve the working directory for interactive agent CLIs.

    This feature replaces the legacy wrapper default of launching from the
    project directory instead of the user's home directory.

    Differences from legacy behavior:
    - Uses the current process working directory when no explicit cwd is passed.
    - Keeps explicit cwd overrides unchanged.
    """
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    return str(base)


def _should_use_proxy(agent_type: str) -> bool:
    """Decide whether an agent should connect through the local MCP proxy.

    This feature replaces the legacy provider split from
    ``agentchattr/apps/server/src/wrapper.py``.

    Differences from legacy behavior:
    - Claude uses direct HTTP MCP config with bearer headers.
    - Codex and Gemini still use DuckDome's local proxy path.
    """
    return agent_type != "claude"


def _resolve_inject_delay(agent_type: str) -> float:
    """Return the per-agent keystroke delay used for console injection.

    This feature replaces the legacy per-provider injection timing from
    ``agentchattr/apps/server/src/wrapper.py``.

    Differences from legacy behavior:
    - Codex keeps a slower Windows-friendly delay so its TUI reliably
      processes the injected prompt before Enter is sent.
    - Other agents keep DuckDome's faster default delay.
    """
    if agent_type == "codex":
        return 0.4
    return 0.03


def _resolve_cmd_shim(cmd: list[str]) -> list[str]:
    """Resolve a .cmd shim to the underlying node command on Windows.

    npm global installs create .cmd shims like::

        @IF EXIST "%~dp0\\node.exe" (
          "%~dp0\\node.exe" "%~dp0\\node_modules\\...\\cli.js" %*
        ) ELSE (
          node "%~dp0\\node_modules\\...\\cli.js" %*
        )

    Running these via shell=True + CREATE_NEW_CONSOLE doesn't work for
    interactive TUI apps because cmd.exe /c interferes with console I/O.
    This function parses the shim to extract the real command.
    """
    exe = shutil.which(cmd[0])
    if exe is None or not exe.lower().endswith(".cmd"):
        return cmd

    try:
        shim_text = Path(exe).read_text(encoding="utf-8")
    except OSError:
        logger.warning("Could not read .cmd shim: %s", exe)
        return cmd

    shim_dir = str(Path(exe).parent)

    # npm .cmd shims come in two common formats. Both end with a line like:
    #   "node.exe" "...cli.js" %*
    # but use either %~dp0 or %dp0% for the directory prefix.
    # We look for the line containing both a .js script and %*, then resolve
    # the directory variable to the actual shim directory.
    for line in shim_text.splitlines():
        stripped = line.strip()
        if "%*" not in stripped:
            continue
        if ".js" not in stripped.lower():
            continue

        # Extract just the command portion (after any || or & chains)
        for sep in ("||", "&"):
            if sep in stripped:
                stripped = stripped.split(sep)[-1].strip()

        # Replace directory variables with actual shim directory
        for var in ("%~dp0\\", "%~dp0/", "%dp0%\\", "%dp0%/"):
            stripped = stripped.replace(var, shim_dir + "\\")

        # Remove %* and trailing whitespace
        stripped = stripped.replace("%*", "").strip()

        # Replace %_prog% with node.exe from shim directory (or just "node")
        node_exe = os.path.join(shim_dir, "node.exe")
        if os.path.isfile(node_exe):
            stripped = stripped.replace("%_prog%", node_exe)
        else:
            stripped = stripped.replace("%_prog%", "node")

        # Split into parts, respecting quotes
        parts = []
        in_quote = False
        current = ""
        for ch in stripped:
            if ch == '"':
                in_quote = not in_quote
            elif ch == " " and not in_quote:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += ch
        if current:
            parts.append(current)

        if not parts:
            continue

        # Append original extra args (everything after cmd[0])
        result = parts + cmd[1:]
        logger.info("Resolved .cmd shim %s -> %s", cmd[0], result)
        return result

    logger.warning("Could not parse .cmd shim: %s", exe)
    return cmd

QUEUE_POLL_INTERVAL = 2.0  # seconds
QUEUE_MONITOR_INTERVAL = 5.0  # seconds
HEARTBEAT_INTERVAL = 5.0  # seconds
INJECT_DELAY = 0.01  # seconds between keystrokes


def _build_trigger_prompt(*, agent_type: str, channel: str, sender: str, text: str) -> str:
    """Build the injected task prompt for an agent queue entry.

    This feature replaces the legacy wrapper prompt in
    ``agentchattr/apps/server/src/wrapper.py``.

    Differences from legacy behavior:
    - DuckDome avoids the literal ``mcp read`` phrasing for Claude because newer
      Claude Code interprets it as a generic MCP resource read, not the legacy
      chat action.
    - Includes the triggering sender/text explicitly so the agent does not have to
      infer the task only from recent chat history.
    - Tells the agent to do the requested work before posting a reply.
    """
    normalized_channel = str(channel).strip() or "general"
    normalized_sender = str(sender).strip() or "human"
    normalized_text = str(text).strip()

    if agent_type == "claude":
        prompt = (
            f'Use DuckDome MCP: chat_join(channel="{normalized_channel}", agent_type="claude"), '
            f'then chat_read(channel="{normalized_channel}"). '
        )
        if normalized_text:
            prompt += f"{normalized_sender} asks: {normalized_text} "
        else:
            prompt += f"Triggered by {normalized_sender}. "
        prompt += "Do the work, then reply with chat_send."
        return prompt

    prompt = (
        f'Use the chat_join tool with channel="{normalized_channel}" and agent_type="{agent_type}", '
        "then use chat_read to get the latest messages in context. "
        f'You were triggered by {normalized_sender}. '
    )

    if normalized_text:
        prompt += f"Requested work: {normalized_text}\n\n"
    else:
        prompt += "Requested work was not included in the queue entry.\n\n"

    prompt += (
        "Complete the requested work before replying. "
        "If the task requires tools, use them. "
        "When you have a substantive update or result, send it with chat_send."
    )
    return prompt


def _open_agent_terminal(tmux_session: str) -> None:
    """Open a visible terminal window attached to the agent's tmux session.

    On macOS: opens a new Terminal.app window that attaches to the session.
    On Linux: no-op — user can attach manually with tmux attach -t <session>.
    On Windows: not used (agents use CREATE_NEW_CONSOLE instead).
    """
    if sys.platform != "darwin":
        return
    marker = f"DuckDome:{tmux_session}"
    # Tag the tab title with a DuckDome marker so we can close only windows
    # opened by DuckDome during shutdown.
    attach_cmd = (
        f"printf '\\033]0;%s\\007' {shlex.quote(marker)}; "
        f"tmux attach-session -t {shlex.quote(tmux_session)}; "
        "exit"
    )
    # Tell Terminal.app to open a new window running the attach command.
    # The window title will show the session name; closing the window leaves
    # the tmux session (and the agent) running in the background.
    # AppleScript requires double-quoted strings; shlex single-quotes are invalid.
    # Use JSON string quoting so backslashes/quotes in the shell command don't
    # break AppleScript parsing (for example with ANSI escape sequences).
    script = f"tell application \"Terminal\" to do script {json.dumps(attach_cmd)}"
    try:
        subprocess.Popen(["osascript", "-e", script])
    except Exception:
        logger.warning("[%s] could not open Terminal.app window", tmux_session)


def _close_agent_terminal(tmux_session: str) -> None:
    """Close Terminal.app windows opened for a DuckDome tmux session."""
    if sys.platform != "darwin":
        return
    marker = f"DuckDome:{tmux_session}"
    marker_literal = json.dumps(marker)
    script = f'''
tell application "Terminal"
  repeat with w in windows
    try
      repeat with t in tabs of w
        set tabName to name of t
        if tabName contains {marker_literal} then
          close t
        end if
      end repeat
    end try
  end repeat
end tell
'''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        logger.warning("[%s] could not close Terminal.app window", tmux_session)


@dataclass
class AgentProcess:
    agent_type: str
    proc: subprocess.Popen | None = None
    pid: int | None = None
    tmux_session: str | None = None
    proxy: McpProxy | None = None
    active_channel: str = "general"
    queue_thread: threading.Thread | None = None
    queue_monitor_thread: threading.Thread | None = None
    heartbeat_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    ready_event: threading.Event = field(default_factory=threading.Event)
    started_at: float | None = None
    inject_delay: float = 0.03
    presence_channel: str | None = None
    console_monitor: ConsoleMonitor | None = None


class AgentProcessManager:
    """Manages long-lived agent CLI processes."""

    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        mcp_host: str = "127.0.0.1",
        app_port: int = 8000,
        tool_approval_service=None,
    ) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config_dir = data_dir / "mcp-configs"
        self._mcp_url = f"http://{mcp_host}:{mcp_port}/mcp"
        self._app_port = app_port
        self._tool_approval_service = tool_approval_service
        self._agents: dict[str, AgentProcess] = {}
        self._starting: set[str] = set()
        self._lock = threading.Lock()

    def start_agent(
        self,
        agent_type: str,
        cwd: str | None = None,
        auto_restart: bool = True,
    ) -> bool:
        """Start a persistent agent process.

        Returns True if started, False if already running.
        """
        with self._lock:
            if agent_type in self._starting:
                logger.info("[%s] start already in progress", agent_type)
                return False
            if agent_type in self._agents and self._is_alive(agent_type):
                logger.info("[%s] already running (pid=%s)", agent_type, self._agents[agent_type].pid)
                return False
            self._starting.add(agent_type)

        try:
            return self._start_agent_inner(agent_type, cwd, auto_restart)
        except Exception:
            logger.exception("[%s] start_agent failed", agent_type)
            return False
        finally:
            with self._lock:
                self._starting.discard(agent_type)

    def _start_agent_inner(
        self,
        agent_type: str,
        cwd: str | None,
        auto_restart: bool,
    ) -> bool:
        proxy: McpProxy | None = None
        mcp_target_url = self._mcp_url
        if _should_use_proxy(agent_type):
            # Start MCP proxy for this agent (gates tool calls through approval).
            proxy = McpProxy(
                upstream_url=self._mcp_url,
                agent_name=agent_type,
                app_port=self._app_port,
            )
            if not proxy.start():
                logger.error("[%s] failed to start MCP proxy", agent_type)
                return False
            mcp_target_url = proxy.mcp_url
            logger.info("[%s] MCP proxy at %s", agent_type, mcp_target_url)
        else:
            logger.info("[%s] using direct MCP at %s", agent_type, mcp_target_url)

        # Generate MCP config pointing to the proxy (not the real MCP server).
        # Including a static Bearer token suppresses Claude Code's OAuth
        # discovery flow, which would otherwise block startup with an
        # interactive auth prompt for a headless background process.
        token = generate_agent_token()
        if agent_type == "gemini":
            mcp_config_path = generate_gemini_settings(
                self._config_dir, agent_type, mcp_target_url, token
            )
        else:
            mcp_config_path = generate_mcp_config(
                self._config_dir, agent_type, mcp_target_url, token
            )

        # Build CLI args
        launch = build_launch_args(
            agent_type, mcp_config_path, cwd, mcp_url=mcp_target_url
        )

        # Resolve .cmd shims to the underlying node command on Windows.
        # Running the .cmd via shell=True + CREATE_NEW_CONSOLE doesn't work
        # for interactive TUI apps (cmd.exe /c interferes with console I/O).
        # Instead, resolve to the actual executable so we can launch directly.
        final_cmd = list(launch.cmd)
        if sys.platform == "win32":
            final_cmd = _resolve_cmd_shim(final_cmd)

        env = {**os.environ, **launch.env}

        # On Windows, each agent needs its own console window for keystroke injection
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_CONSOLE

        agent_proc = AgentProcess(
            agent_type=agent_type,
            proxy=proxy,
            inject_delay=_resolve_inject_delay(agent_type),
        )

        def _run_one_popen_iteration() -> bool:
            """Run one lifecycle via Popen (Windows). Returns False to stop retrying."""
            launch_cwd = _resolve_launch_cwd(cwd)
            logger.info("[%s] starting process: %s", agent_type, " ".join(final_cmd))
            try:
                proc = subprocess.Popen(
                    final_cmd,
                    cwd=launch_cwd,
                    env=env,
                    creationflags=creation_flags,
                )
                agent_proc.proc = proc
                agent_proc.pid = proc.pid
                agent_proc.started_at = time.time()
                agent_proc.ready_event.set()
                logger.info("[%s] process started pid=%d", agent_type, proc.pid)

                # Start console monitor for permission prompt capture (Windows)
                if self._tool_approval_service is not None:
                    monitor = ConsoleMonitor(
                        pid=proc.pid,
                        agent_type=agent_type,
                        channel_id=agent_proc.active_channel,
                        approval_service=self._tool_approval_service,
                        inject_delay=agent_proc.inject_delay,
                    )
                    agent_proc.console_monitor = monitor
                    monitor.start()

                proc.wait()
                logger.warning("[%s] process exited (code=%s)", agent_type, proc.returncode)
                return True
            except FileNotFoundError:
                logger.error("[%s] CLI not found in PATH", agent_type)
                return False
            except Exception:
                logger.exception("[%s] process error", agent_type)
                return True

        def _run_one_tmux_iteration() -> bool:
            """Run one lifecycle in a tmux session (Mac/Linux). Returns False to stop retrying."""
            session = f"duckdome-{agent_type}"
            abs_cwd = _resolve_launch_cwd(cwd)

            # Build shell command; prefix agent-specific env vars using env(1).
            # subprocess.run(env=...) only affects the tmux client binary —
            # the new session inherits from the tmux server, not the client.
            cmd_str = " ".join(shlex.quote(c) for c in final_cmd)
            if launch.env:
                env_prefix = " ".join(
                    f"{shlex.quote(k)}={shlex.quote(v)}" for k, v in launch.env.items()
                )
                cmd_str = f"env {env_prefix} {cmd_str}"

            logger.info("[%s] starting tmux session %s: %s", agent_type, session, cmd_str)

            # Kill any stale session from a previous run
            subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)

            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", session, "-c", abs_cwd, cmd_str],
                capture_output=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                logger.error("[%s] failed to create tmux session: %s", agent_type, stderr)
                return False

            # Capture the shell PID inside the pane for reference
            pid_out = subprocess.run(
                ["tmux", "display-message", "-p", "-t", session, "#{pane_pid}"],
                capture_output=True, text=True,
            ).stdout.strip()
            try:
                agent_proc.pid = int(pid_out)
            except ValueError:
                agent_proc.pid = None

            agent_proc.tmux_session = session
            agent_proc.started_at = time.time()
            agent_proc.ready_event.set()
            logger.info(
                "[%s] tmux session started: %s (pid=%s)", agent_type, session, agent_proc.pid
            )

            # Open a visible terminal window attached to this tmux session
            _open_agent_terminal(session)

            # Poll until the session exits
            while not agent_proc.stop_event.is_set():
                alive = subprocess.run(
                    ["tmux", "has-session", "-t", session], capture_output=True,
                ).returncode == 0
                if not alive:
                    break
                agent_proc.stop_event.wait(1.0)

            logger.warning("[%s] tmux session ended: %s", agent_type, session)
            return True

        def _run_loop():
            try:
                while not agent_proc.stop_event.is_set():
                    if sys.platform == "win32":
                        should_retry = _run_one_popen_iteration()
                    else:
                        should_retry = _run_one_tmux_iteration()

                    if not should_retry or not auto_restart or agent_proc.stop_event.is_set():
                        break
                    logger.info("[%s] restarting in 5s...", agent_type)
                    agent_proc.stop_event.wait(5.0)
            finally:
                # Always unblock the queue watcher and mark stop, regardless of exit path.
                agent_proc.stop_event.set()
                agent_proc.ready_event.set()

        # Start process thread
        proc_thread = threading.Thread(target=_run_loop, daemon=True, name=f"agent-{agent_type}")
        proc_thread.start()

        # Start wrapper helper loops.
        self._start_queue_watcher_thread(agent_proc)
        queue_monitor_thread = threading.Thread(
            target=self._queue_monitor_loop,
            args=(agent_proc,),
            daemon=True,
            name=f"queue-monitor-{agent_type}",
        )
        queue_monitor_thread.start()
        agent_proc.queue_monitor_thread = queue_monitor_thread
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(agent_proc,),
            daemon=True,
            name=f"heartbeat-{agent_type}",
        )
        heartbeat_thread.start()
        agent_proc.heartbeat_thread = heartbeat_thread

        with self._lock:
            self._agents[agent_type] = agent_proc

        return True

    def stop_agent(self, agent_type: str) -> bool:
        """Stop a persistent agent process."""
        with self._lock:
            agent_proc = self._agents.pop(agent_type, None)

        if agent_proc is None:
            return False

        agent_proc.stop_event.set()
        if agent_proc.console_monitor:
            agent_proc.console_monitor.stop()
        if sys.platform != "win32" and agent_proc.tmux_session:
            logger.info("[%s] killing tmux session %s", agent_type, agent_proc.tmux_session)
            subprocess.run(
                ["tmux", "kill-session", "-t", agent_proc.tmux_session], capture_output=True
            )
            _close_agent_terminal(agent_proc.tmux_session)
        elif agent_proc.proc and agent_proc.proc.poll() is None:
            logger.info("[%s] terminating pid=%d", agent_type, agent_proc.pid)
            agent_proc.proc.terminate()
            try:
                agent_proc.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                agent_proc.proc.kill()
        if agent_proc.proxy:
            try:
                agent_proc.proxy.stop()
            except Exception:
                logger.exception("[%s] proxy shutdown error", agent_type)
        self._deregister_agent_presence(agent_proc)
        return True

    def stop_all(self) -> None:
        """Stop all agent processes."""
        with self._lock:
            agent_types = list(self._agents.keys())
        for at in agent_types:
            self.stop_agent(at)

    def is_running(self, agent_type: str) -> bool:
        with self._lock:
            return agent_type in self._agents and self._is_alive(agent_type)

    def list_running(self) -> list[str]:
        with self._lock:
            return [at for at in self._agents if self._is_alive(at)]

    def trigger_agent(self, agent_type: str, sender: str, text: str, channel: str) -> bool:
        """Write a queue entry for the agent. Returns True if agent is running."""
        from duckdome.wrapper.queue import write_queue_entry

        if not self.is_running(agent_type):
            return False
        write_queue_entry(self._data_dir, agent_type, sender, text, channel)
        return True

    def _is_alive(self, agent_type: str) -> bool:
        ap = self._agents.get(agent_type)
        if ap is None:
            return False
        if sys.platform != "win32" and ap.tmux_session:
            return subprocess.run(
                ["tmux", "has-session", "-t", ap.tmux_session], capture_output=True,
            ).returncode == 0
        return ap.proc is not None and ap.proc.poll() is None

    def _app_url(self, path: str) -> str:
        return f"http://127.0.0.1:{self._app_port}{path}"

    def _resolve_presence_channel(self, agent_proc: AgentProcess) -> str | None:
        if agent_proc.proxy is not None and agent_proc.proxy._has_joined_channel():
            return agent_proc.proxy._get_joined_channel()
        return agent_proc.presence_channel

    def _deregister_agent_presence(self, agent_proc: AgentProcess) -> bool:
        channel = self._resolve_presence_channel(agent_proc)
        if not channel:
            return False

        payload = json.dumps({
            "channel_id": channel,
            "agent_type": agent_proc.agent_type,
        }).encode("utf-8")
        req = Request(
            self._app_url("/api/agents/deregister"),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except HTTPError as exc:
            if exc.code != 404:
                logger.warning("[%s] deregister failed: %s", agent_proc.agent_type, exc)
        except (URLError, OSError) as exc:
            logger.warning("[%s] deregister failed: %s", agent_proc.agent_type, exc)
        return False

    def _start_queue_watcher_thread(self, agent_proc: AgentProcess) -> None:
        queue_thread = threading.Thread(
            target=self._queue_watcher,
            args=(agent_proc,),
            daemon=True,
            name=f"queue-{agent_proc.agent_type}",
        )
        queue_thread.start()
        agent_proc.queue_thread = queue_thread

    def _post_agent_heartbeat(self, agent_proc: AgentProcess) -> bool:
        """Refresh channel-scoped agent presence after chat_join.

        This feature replaces the legacy wrapper heartbeat loop in
        ``agentchattr/apps/server/src/wrapper.py``.

        Differences from legacy behavior:
        - DuckDome reports channel_id + agent_type instead of a mutable wrapper name.
        - Heartbeats are best-effort and begin only after the proxy has observed
          a joined channel.
        """
        channel = agent_proc.active_channel
        if agent_proc.proxy is not None:
            channel = agent_proc.proxy._get_joined_channel() or channel
        if not channel or channel == "general":
            return False

        payload = json.dumps({
            "channel_id": channel,
            "agent_type": agent_proc.agent_type,
        }).encode("utf-8")
        req = Request(
            self._app_url("/api/agents/heartbeat"),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except HTTPError as exc:
            if exc.code != 404:
                logger.warning("[%s] heartbeat failed: %s", agent_proc.agent_type, exc)
        except (URLError, OSError) as exc:
            logger.warning("[%s] heartbeat failed: %s", agent_proc.agent_type, exc)
        return False

    def _heartbeat_loop(self, agent_proc: AgentProcess) -> None:
        agent_type = agent_proc.agent_type
        logger.info("[%s] heartbeat waiting for process to start", agent_type)
        agent_proc.ready_event.wait()
        logger.info("[%s] heartbeat started", agent_type)

        while not agent_proc.stop_event.is_set():
            self._post_agent_heartbeat(agent_proc)
            agent_proc.stop_event.wait(HEARTBEAT_INTERVAL)

        logger.info("[%s] heartbeat stopped", agent_type)

    def _queue_monitor_loop(self, agent_proc: AgentProcess) -> None:
        agent_type = agent_proc.agent_type
        logger.info("[%s] queue monitor waiting for process to start", agent_type)
        agent_proc.ready_event.wait()
        logger.info("[%s] queue monitor started", agent_type)

        while not agent_proc.stop_event.is_set():
            agent_proc.stop_event.wait(QUEUE_MONITOR_INTERVAL)
            if agent_proc.stop_event.is_set():
                break
            if not self._is_alive(agent_type):
                continue
            queue_thread = agent_proc.queue_thread
            if queue_thread and queue_thread.is_alive():
                continue
            logger.warning("[%s] queue watcher stopped unexpectedly; restarting", agent_type)
            self._start_queue_watcher_thread(agent_proc)

        logger.info("[%s] queue monitor stopped", agent_type)

    def _queue_watcher(self, agent_proc: AgentProcess) -> None:
        """Poll queue file and inject text into the agent's console."""
        agent_type = agent_proc.agent_type
        logger.info("[%s] queue watcher waiting for process to start", agent_type)
        # Wait for the process to actually start before polling the queue
        agent_proc.ready_event.wait()
        logger.info("[%s] queue watcher started", agent_type)

        while not agent_proc.stop_event.is_set():
            agent_proc.stop_event.wait(QUEUE_POLL_INTERVAL)
            if agent_proc.stop_event.is_set():
                break

            if not self._is_alive(agent_type):
                continue

            entries = read_queue_entries(self._data_dir, agent_type)
            if not entries:
                continue

            for entry in entries:
                channel = entry.get("channel", "general")
                text = entry.get("text", "")
                sender = entry.get("sender", "human")
                agent_proc.active_channel = str(channel).strip() or "general"
                agent_proc.presence_channel = agent_proc.active_channel
                if agent_proc.console_monitor:
                    agent_proc.console_monitor.channel_id = agent_proc.active_channel
                injection = _build_trigger_prompt(
                    agent_type=agent_type,
                    channel=channel,
                    sender=sender,
                    text=text,
                )
                logger.info("[%s] injecting prompt for channel=%s", agent_type, channel)
                try:
                    if sys.platform == "win32":
                        success = inject(
                            injection,
                            agent_proc.pid,
                            delay=agent_proc.inject_delay,
                        )
                    else:
                        success = inject(
                            injection,
                            delay=agent_proc.inject_delay,
                            tmux_session=agent_proc.tmux_session,
                        )
                    if not success:
                        logger.warning("[%s] injection returned False for channel=%s", agent_type, channel)
                except Exception:
                    logger.exception("[%s] injection failed", agent_type)

        logger.info("[%s] queue watcher stopped", agent_type)
