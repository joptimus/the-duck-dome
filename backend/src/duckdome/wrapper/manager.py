"""Manages persistent interactive CLI processes for each agent.

Each agent gets:
- A subprocess.Popen process (Windows) or tmux session (Mac/Linux)
- A QueueWatcher thread that polls its queue file
- A MCP config file pointing to the DuckDome MCP server
"""
from __future__ import annotations

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

from duckdome.wrapper.injector import inject
from duckdome.wrapper.mcp_config import generate_agent_token, generate_gemini_settings, generate_mcp_config
from duckdome.wrapper.mcp_proxy import McpProxy
from duckdome.wrapper.providers import build_launch_args
from duckdome.wrapper.queue import read_queue_entries

logger = logging.getLogger(__name__)


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
INJECT_DELAY = 0.01  # seconds between keystrokes


def _open_agent_terminal(tmux_session: str) -> None:
    """Open a visible terminal window attached to the agent's tmux session.

    On macOS: opens a new Terminal.app window that attaches to the session.
    On Linux: no-op — user can attach manually with tmux attach -t <session>.
    On Windows: not used (agents use CREATE_NEW_CONSOLE instead).
    """
    if sys.platform != "darwin":
        return
    attach_cmd = f"tmux attach-session -t {tmux_session}"
    # Tell Terminal.app to open a new window running the attach command.
    # The window title will show the session name; closing the window leaves
    # the tmux session (and the agent) running in the background.
    # AppleScript requires double-quoted strings; shlex single-quotes are invalid.
    script = f'tell application "Terminal" to do script "{attach_cmd}"'
    try:
        subprocess.Popen(["osascript", "-e", script])
    except Exception:
        logger.warning("[%s] could not open Terminal.app window", tmux_session)


@dataclass
class AgentProcess:
    agent_type: str
    proc: subprocess.Popen | None = None
    pid: int | None = None
    tmux_session: str | None = None
    proxy: McpProxy | None = None
    queue_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    ready_event: threading.Event = field(default_factory=threading.Event)
    started_at: float | None = None


class AgentProcessManager:
    """Manages long-lived agent CLI processes."""

    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        mcp_host: str = "127.0.0.1",
        app_port: int = 8000,
    ) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config_dir = data_dir / "mcp-configs"
        self._mcp_url = f"http://{mcp_host}:{mcp_port}/mcp"
        self._app_port = app_port
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

        # Start MCP proxy for this agent (gates tool calls through approval)
        proxy = McpProxy(
            upstream_url=self._mcp_url,
            agent_name=agent_type,
            app_port=self._app_port,
        )
        if not proxy.start():
            logger.error("[%s] failed to start MCP proxy", agent_type)
            with self._lock:
                self._starting.discard(agent_type)
            return False
        proxy_mcp_url = proxy.mcp_url
        logger.info("[%s] MCP proxy at %s", agent_type, proxy_mcp_url)

        # Generate MCP config pointing to the proxy (not the real MCP server).
        # Including a static Bearer token suppresses Claude Code's OAuth
        # discovery flow, which would otherwise block startup with an
        # interactive auth prompt for a headless background process.
        token = generate_agent_token()
        if agent_type == "gemini":
            mcp_config_path = generate_gemini_settings(
                self._config_dir, agent_type, proxy_mcp_url, token
            )
        else:
            mcp_config_path = generate_mcp_config(
                self._config_dir, agent_type, proxy_mcp_url, token
            )

        # Build CLI args
        launch = build_launch_args(
            agent_type, mcp_config_path, cwd, mcp_url=proxy_mcp_url
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

        agent_proc = AgentProcess(agent_type=agent_type, proxy=proxy)

        def _run_one_popen_iteration() -> bool:
            """Run one lifecycle via Popen (Windows). Returns False to stop retrying."""
            logger.info("[%s] starting process: %s", agent_type, " ".join(final_cmd))
            try:
                proc = subprocess.Popen(
                    final_cmd,
                    cwd=cwd,
                    env=env,
                    creationflags=creation_flags,
                )
                agent_proc.proc = proc
                agent_proc.pid = proc.pid
                agent_proc.started_at = time.time()
                agent_proc.ready_event.set()
                logger.info("[%s] process started pid=%d", agent_type, proc.pid)
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
            abs_cwd = str(Path(cwd).resolve()) if cwd else str(Path.home())

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

        # Start queue watcher
        queue_thread = threading.Thread(
            target=self._queue_watcher,
            args=(agent_proc,),
            daemon=True,
            name=f"queue-{agent_type}",
        )
        queue_thread.start()
        agent_proc.queue_thread = queue_thread

        with self._lock:
            self._agents[agent_type] = agent_proc
            self._starting.discard(agent_type)

        return True

    def stop_agent(self, agent_type: str) -> bool:
        """Stop a persistent agent process."""
        with self._lock:
            agent_proc = self._agents.pop(agent_type, None)

        if agent_proc is None:
            return False

        agent_proc.stop_event.set()
        if sys.platform != "win32" and agent_proc.tmux_session:
            logger.info("[%s] killing tmux session %s", agent_type, agent_proc.tmux_session)
            subprocess.run(
                ["tmux", "kill-session", "-t", agent_proc.tmux_session], capture_output=True
            )
        elif agent_proc.proc and agent_proc.proc.poll() is None:
            logger.info("[%s] terminating pid=%d", agent_type, agent_proc.pid)
            agent_proc.proc.terminate()
            try:
                agent_proc.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                agent_proc.proc.kill()
        if agent_proc.proxy:
            agent_proc.proxy.stop()
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

            entries = read_queue_entries(self._data_dir, agent_type)
            if not entries:
                continue

            if not self._is_alive(agent_type):
                logger.warning("[%s] queue has entries but process not running", agent_type)
                continue

            for entry in entries:
                channel = entry.get("channel", "general")
                text = entry.get("text", "")
                # Tell the agent to use chat_join + chat_read tools (not "mcp read" which
                # Claude Code now interprets as a resource read request)
                injection = (
                    f"Use the chat_join tool with channel=\"{channel}\" and agent_type=\"{agent_type}\", "
                    f"then use chat_read to see messages, then respond with chat_send."
                )
                logger.info("[%s] injecting prompt for channel=%s", agent_type, channel)
                try:
                    if sys.platform == "win32":
                        success = inject(injection, agent_proc.pid, delay=INJECT_DELAY)
                    else:
                        success = inject(
                            injection, delay=INJECT_DELAY, tmux_session=agent_proc.tmux_session
                        )
                    if not success:
                        logger.warning("[%s] injection returned False for channel=%s", agent_type, channel)
                except Exception:
                    logger.exception("[%s] injection failed", agent_type)

        logger.info("[%s] queue watcher stopped", agent_type)
