"""Manages persistent interactive CLI processes for each agent.

Each agent gets:
- A subprocess.Popen process (Windows) or tmux session (Mac/Linux)
- A QueueWatcher thread that polls its queue file
- A MCP config file pointing to the DuckDome MCP server
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from duckdome.bridges.base import AgentBridge, AgentConfig
from duckdome.bridges.codex_bridge import CodexBridge
from duckdome.bridges.claude_bridge import ClaudeBridge
from duckdome.bridges.events import (
    AgentMessageDeltaEvent,
    AgentMessageEvent,
    AgentStatus,
    ApprovalRequestEvent,
    ErrorEvent,
    StatusChangeEvent,
    SubagentEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from duckdome.wrapper.console_monitor import ConsoleMonitor
from duckdome.wrapper.injector import inject
from duckdome.mcp.auth import agent_auth_store
from duckdome.wrapper.mcp_config import generate_agent_token, generate_gemini_settings, generate_mcp_config
from duckdome.wrapper.mcp_proxy import McpProxy
from duckdome.wrapper.providers import build_launch_args
from duckdome.wrapper.queue import read_queue_entries
from duckdome.wrapper.safe_tools import claude_allowed_mcp_tools

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
        return 1.5
    return 0.05


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


def _build_startup_prompt(*, agent_type: str, channel: str) -> str:
    """Build the one-time startup prompt sent when a bridge agent becomes ready.

    Establishes the agent's identity and channel context so trigger prompts
    can be kept minimal.
    """
    return (
        f'You are the {agent_type} agent for the #{channel} channel in DuckDome. '
        f'Use chat_read to read messages and chat_send to reply. '
        f'Always pass sender="{agent_type}" in your tool calls. '
        f'You can @mention other agents to involve them in tasks.'
    )


def _build_trigger_prompt(*, agent_type: str, channel: str, sender: str, text: str) -> str:
    """Build the injected task prompt when an agent is mentioned.

    The agent already knows its channel and identity from the startup prompt,
    so this just needs to wake it up.
    """
    return "you were mentioned, take appropriate action"


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


def _win_get_process_tree_pids(root_pid: int) -> set[int]:
    """Return *root_pid* plus all its descendant PIDs on Windows.

    Uses WMI via ``wmic`` (available on all Windows versions) to walk the
    process tree without requiring ``psutil``.
    """
    pids: set[int] = {root_pid}
    if sys.platform != "win32":
        return pids
    try:
        # Build parent→children map from wmic
        out = subprocess.check_output(
            ["wmic", "process", "get", "ProcessId,ParentProcessId", "/format:csv"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        children: dict[int, list[int]] = {}
        for line in out.strip().splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                ppid, cpid = int(parts[1]), int(parts[2])
            except ValueError:
                continue
            children.setdefault(ppid, []).append(cpid)
        # BFS from root
        queue = [root_pid]
        while queue:
            p = queue.pop()
            for c in children.get(p, []):
                if c not in pids:
                    pids.add(c)
                    queue.append(c)
    except Exception:
        pass
    return pids


def _win_set_window_visible(pid: int, visible: bool) -> None:
    """Show or hide the console window for a process on Windows (no-op on other platforms).

    Searches windows owned by the process AND all its child processes
    (the console window is often owned by conhost.exe, a child of the agent).
    """
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    SW_HIDE = 0
    SW_SHOW = 5
    user32 = ctypes.windll.user32

    target_pids = _win_get_process_tree_pids(pid)
    found: list[int] = []

    WinEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd: int, _: int) -> bool:
        pid_out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value in target_pids:
            found.append(hwnd)
        return True

    user32.EnumWindows(WinEnumProc(_cb), 0)
    for hwnd in found:
        user32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)


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
    key: str = ""  # compound key: "agent_type:channel_id"


class AgentProcessManager:
    """Manages long-lived agent CLI processes."""

    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        mcp_host: str = "127.0.0.1",
        app_port: int = 8000,
        tool_approval_service=None,
        ws_manager=None,
        message_service=None,
        trigger_service=None,
    ) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config_dir = data_dir / "mcp-configs"
        self._mcp_url = f"http://{mcp_host}:{mcp_port}/mcp"
        self._app_port = app_port
        self._tool_approval_service = tool_approval_service
        self._ws_manager = ws_manager
        self._message_service = message_service
        self._trigger_service = trigger_service
        self._agents: dict[str, AgentProcess] = {}
        self._bridges: dict[str, AgentBridge] = {}
        self._bridge_details: dict[str, dict[str, object | None]] = {}
        self._starting: set[str] = set()
        self._lock = threading.Lock()
        self._show_windows: bool = False
        self._bridge_loop: asyncio.AbstractEventLoop | None = None
        self._bridge_loop_thread: threading.Thread | None = None
        self._bridge_loop_thread_id: int | None = None
        self._bridge_loop_ready = threading.Event()

    @staticmethod
    def _agent_key(agent_type: str, channel_id: str = "") -> str:
        """Build the dict key for an agent process.

        Uses ``--`` as separator instead of ``:`` because colons are
        illegal in Windows file paths and the key is also used as the
        queue file name.
        """
        return f"{agent_type}--{channel_id}" if channel_id else agent_type

    @staticmethod
    def _use_bridge(agent_type: str) -> bool:
        """Return True if this agent type should use the new bridge path."""
        return agent_type in ("codex", "claude")

    def _create_bridge(self, agent_type: str, channel_id: str) -> AgentBridge:
        if agent_type == "codex":
            return CodexBridge()
        if agent_type == "claude":
            return ClaudeBridge(receiver_port=self._app_port)
        raise ValueError(f"No bridge for agent type: {agent_type}")

    def _connect_bridge_events(self, bridge: AgentBridge, key: str) -> None:
        """Wire bridge events to the existing WebSocket broadcast + approval systems."""

        def _on_status_change(event: StatusChangeEvent) -> None:
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_status_change",
                    "agent_id": f"{event.channel_id}:{event.agent_type}",
                    "status": event.status.value,
                })

        def _on_approval_request(event: ApprovalRequestEvent) -> None:
            if self._tool_approval_service is None:
                return
            result = self._tool_approval_service.request(
                agent=event.agent_type,
                tool=event.tool_name,
                arguments=event.tool_input,
                channel=event.channel_id,
            )
            # If policy auto-resolved, respond immediately
            if result.status == "approved":
                self._submit_bridge_coro(bridge.approve(event.approval_id))
            elif result.status == "denied":
                self._submit_bridge_coro(
                    bridge.deny(event.approval_id, "Denied by policy")
                )
            elif result.approval is not None:
                self._tool_approval_service.register_runtime_resolver(
                    result.approval.id,
                    lambda decision, reason: self._submit_bridge_coro(
                        bridge.approve(event.approval_id)
                        if decision == "approved"
                        else bridge.deny(
                            event.approval_id,
                            reason or "Denied by user",
                        )
                    ),
                )
            # If "pending", the UI will call approve/deny via the tool approval route

        def _on_message(event: AgentMessageEvent) -> None:
            if self._message_service is None:
                return
            try:
                msg = self._message_service.send(
                    text=event.text,
                    channel=event.channel_id,
                    sender=event.agent_type,
                )
                self._message_service.process_agent_response(
                    agent_name=event.agent_type,
                    channel=event.channel_id,
                    response_id=msg.id,
                )
            except Exception:
                logger.exception(
                    "Failed to persist bridge message: agent=%s channel=%s",
                    event.agent_type,
                    event.channel_id,
                )

        def _on_message_delta(event: AgentMessageDeltaEvent) -> None:
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_message_delta",
                    "agent_id": event.agent_id,
                    "agent_type": event.agent_type,
                    "channel_id": event.channel_id,
                    "delta": event.delta,
                    "timestamp": event.timestamp,
                })

        def _on_tool_call(event: ToolCallEvent) -> None:
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_tool_call",
                    "agent_id": event.agent_id,
                    "agent_type": event.agent_type,
                    "channel_id": event.channel_id,
                    "tool_name": event.tool_name,
                    "tool_input": event.tool_input,
                    "call_id": event.call_id,
                    "timestamp": event.timestamp,
                })

        def _on_tool_result(event: ToolResultEvent) -> None:
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_tool_result",
                    "agent_id": event.agent_id,
                    "agent_type": event.agent_type,
                    "channel_id": event.channel_id,
                    "tool_name": event.tool_name,
                    "call_id": event.call_id,
                    "success": event.success,
                    "output": event.output,
                    "duration_ms": event.duration_ms,
                    "timestamp": event.timestamp,
                })

        def _on_subagent(event: SubagentEvent) -> None:
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_subagent",
                    "agent_id": event.agent_id,
                    "agent_type": event.agent_type,
                    "channel_id": event.channel_id,
                    "subagent_id": event.subagent_id,
                    "subagent_type": event.subagent_type,
                    "started": event.started,
                    "last_message": event.last_message,
                    "timestamp": event.timestamp,
                })

        def _on_error(event: ErrorEvent) -> None:
            if self._message_service is not None:
                try:
                    self._message_service.post_system_event(
                        channel=event.channel_id,
                        subtype="error",
                        agent=event.agent_type,
                        text=f"{event.agent_type} error: {event.error}",
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist bridge error: agent=%s channel=%s",
                        event.agent_type,
                        event.channel_id,
                    )
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_error",
                    "agent_id": event.agent_id,
                    "agent_type": event.agent_type,
                    "channel_id": event.channel_id,
                    "error": event.error,
                    "details": event.details,
                    "timestamp": event.timestamp,
                })

        def _handle_claude_pre_tool_use(
            tool_name: str,
            tool_input: dict[str, object],
            channel_id: str,
        ) -> dict[str, str]:
            if self._tool_approval_service is None:
                return {}
            if tool_name in claude_allowed_mcp_tools():
                return {"decision": "approve"}

            result = self._tool_approval_service.request(
                agent="claude",
                tool=tool_name,
                arguments=tool_input,
                channel=channel_id,
            )
            if result.status == "approved":
                return {"decision": "approve"}
            if result.status == "denied":
                return {"decision": "block", "reason": "Denied by policy"}
            if result.approval is None:
                return {}

            wait_event = threading.Event()
            decision: dict[str, str | None] = {"status": None, "reason": None}

            def _resolver(resolved: str, reason: str | None) -> None:
                decision["status"] = resolved
                decision["reason"] = reason
                wait_event.set()

            self._tool_approval_service.register_runtime_resolver(
                result.approval.id,
                _resolver,
            )
            try:
                if not wait_event.wait(timeout=600):
                    return {"decision": "block", "reason": "Approval timed out"}
                if decision["status"] == "approved":
                    return {"decision": "approve"}
                return {
                    "decision": "block",
                    "reason": decision["reason"] or "Denied by user",
                }
            finally:
                self._tool_approval_service.clear_runtime_resolver(result.approval.id)

        bridge.on(bridge.STATUS_CHANGE, _on_status_change)
        bridge.on(bridge.APPROVAL_REQUEST, _on_approval_request)
        bridge.on(bridge.MESSAGE, _on_message)
        bridge.on(bridge.MESSAGE_DELTA, _on_message_delta)
        bridge.on(bridge.TOOL_CALL, _on_tool_call)
        bridge.on(bridge.TOOL_RESULT, _on_tool_result)
        bridge.on(bridge.SUBAGENT, _on_subagent)
        bridge.on(bridge.ERROR, _on_error)
        if isinstance(bridge, ClaudeBridge):
            bridge.set_pre_tool_use_handler(_handle_claude_pre_tool_use)

    def _bridge_loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._bridge_loop = loop
        self._bridge_loop_thread_id = threading.get_ident()
        self._bridge_loop_ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()
            self._bridge_loop = None
            self._bridge_loop_thread_id = None
            self._bridge_loop_ready.clear()

    def _ensure_bridge_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if (
                self._bridge_loop is not None
                and self._bridge_loop_thread is not None
                and self._bridge_loop_thread.is_alive()
            ):
                return self._bridge_loop

            self._bridge_loop_ready.clear()
            self._bridge_loop_thread = threading.Thread(
                target=self._bridge_loop_worker,
                daemon=True,
                name="duckdome-bridge-loop",
            )
            self._bridge_loop_thread.start()

        if not self._bridge_loop_ready.wait(timeout=5):
            raise RuntimeError("Bridge event loop failed to start")
        if self._bridge_loop is None:
            raise RuntimeError("Bridge event loop unavailable")
        return self._bridge_loop

    def _submit_bridge_coro(self, coro: Coroutine[Any, Any, Any]) -> object:
        loop = self._ensure_bridge_loop()
        if self._bridge_loop_thread_id == threading.get_ident():
            return loop.create_task(coro)
        return asyncio.run_coroutine_threadsafe(coro, loop)

    def _run_bridge_coro(
        self,
        coro: Coroutine[Any, Any, Any],
        timeout: float | None = 60,
    ) -> Any:
        future = self._submit_bridge_coro(coro)
        if hasattr(future, "result"):
            return future.result(timeout=timeout)
        raise RuntimeError("Cannot synchronously wait for bridge coroutine on bridge loop thread")

    def _shutdown_bridge_loop(self) -> None:
        with self._lock:
            loop = self._bridge_loop
            thread = self._bridge_loop_thread
        if loop is None or thread is None or not thread.is_alive():
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        with self._lock:
            if self._bridge_loop_thread is thread and not thread.is_alive():
                self._bridge_loop_thread = None

    async def _start_agent_bridge(
        self,
        agent_type: str,
        cwd: str | None,
        channel_id: str,
    ) -> bool:
        """Start an agent using the bridge path (async)."""
        key = self._agent_key(agent_type, channel_id)
        bridge = self._create_bridge(agent_type, channel_id)
        self._connect_bridge_events(bridge, key)

        config = AgentConfig(
            agent_type=agent_type,
            channel_id=channel_id or "general",
            cwd=_resolve_launch_cwd(cwd),
            mcp_url=self._mcp_url,
            extra={
                "mcp_config_path": str(self._config_dir / f"{agent_type}-mcp.json"),
            },
        )
        token = generate_agent_token()
        bound_channel = channel_id or "general"
        agent_auth_store.register(token, channel=bound_channel, agent_type=agent_type)
        config.mcp_url = f"{self._mcp_url}?duckdome_token={token}"
        config.extra["duckdome_token"] = token

        await bridge.start(agent_id=key, config=config)
        with self._lock:
            self._bridges[key] = bridge
            self._bridge_details[key] = {
                "pid": getattr(getattr(bridge, "_proc", None), "pid", None),
                "started_at": time.time(),
                "duckdome_token": token,
            }
        # Register agent in channel — posts "joined the channel" system message
        if self._trigger_service is not None:
            try:
                self._trigger_service.register_agent(bound_channel, agent_type)
            except Exception:
                logger.exception("[%s] failed to register agent in channel %s", key, bound_channel)

        # Send startup prompt — fires once the bridge is ready (ClaudeBridge waits
        # for SessionStart; CodexBridge is ready immediately after start())
        startup = _build_startup_prompt(agent_type=agent_type, channel=bound_channel)
        self._submit_bridge_coro(bridge.send_prompt(startup, bound_channel, "system"))

        logger.info("[%s] started via bridge", key)
        return True

    def start_agent(
        self,
        agent_type: str,
        cwd: str | None = None,
        auto_restart: bool = True,
        channel_id: str = "",
    ) -> bool:
        """Start a persistent agent process.

        When *channel_id* is provided, a separate process is started for
        that channel.  Returns True if started, False if already running.
        """
        key = self._agent_key(agent_type, channel_id)
        with self._lock:
            if key in self._starting:
                logger.info("[%s] start already in progress", key)
                return False
            if key in self._bridges:
                logger.info("[%s] already running via bridge", key)
                return False
            if key in self._agents and self._is_alive(key):
                logger.info("[%s] already running (pid=%s)", key, self._agents[key].pid)
                return False
            self._starting.add(key)

        try:
            if self._use_bridge(agent_type):
                return self._run_bridge_coro(
                    self._start_agent_bridge(agent_type, cwd, channel_id)
                )
            return self._start_agent_inner(agent_type, cwd, auto_restart, channel_id=channel_id)
        except Exception:
            logger.exception("[%s] start_agent failed", key)
            return False
        finally:
            with self._lock:
                self._starting.discard(key)

    def _start_agent_inner(
        self,
        agent_type: str,
        cwd: str | None,
        auto_restart: bool,
        channel_id: str = "",
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
            active_channel=channel_id or "general",
            key=self._agent_key(agent_type, channel_id),
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
                if not self._show_windows:
                    # Brief delay so the console window is created before we hide it
                    time.sleep(0.5)
                    _win_set_window_visible(proc.pid, False)

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

            # Open a visible terminal window attached to this tmux session (if enabled)
            if self._show_windows:
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

        key = self._agent_key(agent_type, channel_id)
        with self._lock:
            self._agents[key] = agent_proc

        return True

    def stop_agent(self, agent_type: str, channel_id: str = "") -> bool:
        """Stop a persistent agent process."""
        key = self._agent_key(agent_type, channel_id)

        # Check bridge path first
        with self._lock:
            bridge = self._bridges.pop(key, None)
            bridge_details = self._bridge_details.pop(key, None)
        if bridge_details and bridge_details.get("duckdome_token"):
            agent_auth_store.unregister(str(bridge_details["duckdome_token"]))
        if bridge is not None:
            self._run_bridge_coro(bridge.stop())
            logger.info("[%s] stopped via bridge", key)
            return True

        with self._lock:
            agent_proc = self._agents.pop(key, None)

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
        """Stop all agent processes (both legacy and bridge-managed)."""
        with self._lock:
            keys = list(self._agents.keys()) + list(self._bridges.keys())
        for key in set(keys):
            # Keys are "agent_type--channel_id" or just "agent_type"
            parts = key.split("--", 1)
            self.stop_agent(parts[0], parts[1] if len(parts) > 1 else "")
        self._shutdown_bridge_loop()

    def is_running(self, agent_type: str, channel_id: str = "") -> bool:
        key = self._agent_key(agent_type, channel_id)
        with self._lock:
            if key in self._bridges:
                return True
            return key in self._agents and self._is_alive(key)

    def list_running(self) -> list[str]:
        with self._lock:
            legacy = [key for key in self._agents if self._is_alive(key)]
            bridged = list(self._bridges.keys())
            return legacy + bridged

    def get_agent_details(self, agent_type: str, channel_id: str = "") -> dict | None:
        """Return pid and started_at for a running agent."""
        key = self._agent_key(agent_type, channel_id)
        with self._lock:
            bridge_details = self._bridge_details.get(key)
            if key in self._bridges and bridge_details is not None:
                return {
                    "pid": bridge_details.get("pid"),
                    "started_at": bridge_details.get("started_at"),
                }
            ap = self._agents.get(key)
            if ap is None or not self._is_alive(key):
                return None
            return {
                "pid": ap.pid,
                "started_at": ap.started_at,
            }

    def set_show_windows(self, visible: bool) -> None:
        """Update window visibility flag and apply immediately to all running agents."""
        self._show_windows = visible
        with self._lock:
            agents = list(self._agents.items())
        for key, ap in agents:
            if not self._is_alive(key):
                continue
            if ap.tmux_session:
                if visible:
                    _open_agent_terminal(ap.tmux_session)
                else:
                    _close_agent_terminal(ap.tmux_session)
            elif ap.pid is not None:
                _win_set_window_visible(ap.pid, visible)

    def trigger_agent(
        self, agent_type: str, sender: str, text: str, channel: str,
        cwd: str | None = None,
    ) -> bool:
        """Trigger the agent for a specific channel.

        If a per-channel process exists, uses it. Otherwise starts one.
        *cwd* is passed through to start_agent when the process is first created.
        Bridge-managed agents use send_prompt() instead of queue files.
        """
        key = self._agent_key(agent_type, channel)
        if not self.is_running(agent_type, channel):
            self.start_agent(agent_type, cwd=cwd, channel_id=channel)

        # Bridge path: send prompt directly
        with self._lock:
            bridge = self._bridges.get(key)
        if bridge is not None:
            prompt = _build_trigger_prompt(
                agent_type=agent_type, channel=channel, sender=sender, text=text,
            )
            try:
                self._run_bridge_coro(
                    bridge.send_prompt(prompt, channel, sender),
                    timeout=120,  # send_prompt waits up to 30s for ready + keystroke injection
                )
            except (TimeoutError, RuntimeError) as exc:
                logger.error("[%s] send_prompt failed: %s", key, exc)
                return False
            return True

        if self._use_bridge(agent_type):
            logger.error("[%s] bridge trigger requested but no bridge is running", key)
            return False

        # Legacy path: write to queue file
        from duckdome.wrapper.queue import write_queue_entry
        write_queue_entry(self._data_dir, key, sender, text, channel)

        # Register agent in channel (triggers "joined" system message)
        # and immediately set status to "working".
        for endpoint in ["/api/agents/register", "/api/agents/heartbeat"]:
            try:
                payload = json.dumps({
                    "channel_id": channel,
                    "agent_type": agent_type,
                }).encode("utf-8")
                req = Request(
                    self._app_url(endpoint),
                    data=payload,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                urlopen(req, timeout=3)
            except Exception:
                pass  # best effort

        # Set stored status to working and broadcast.
        try:
            payload = json.dumps({
                "channel_id": channel,
                "agent_type": agent_type,
                "status": "working",
            }).encode("utf-8")
            req = Request(
                self._app_url("/api/agents/status"),
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            urlopen(req, timeout=3)
        except Exception:
            # Fallback: just broadcast via WS
            if self._ws_manager:
                self._ws_manager.broadcast_sync({
                    "type": "agent_status_change",
                    "agent_id": f"{channel}:{agent_type}",
                    "status": "working",
                })

        return True

    def _is_alive(self, key: str) -> bool:
        ap = self._agents.get(key)
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
        agent_key = agent_proc.key or agent_proc.agent_type
        agent_type = agent_proc.agent_type
        logger.info("[%s] queue watcher waiting for process to start", agent_key)
        # Wait for the process to actually start before polling the queue
        agent_proc.ready_event.wait()
        logger.info("[%s] queue watcher started", agent_key)

        while not agent_proc.stop_event.is_set():
            agent_proc.stop_event.wait(QUEUE_POLL_INTERVAL)
            if agent_proc.stop_event.is_set():
                break

            if not self._is_alive(agent_key):
                continue

            entries = read_queue_entries(self._data_dir, agent_key)
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
