"""Per-agent console monitor for permission prompt capture.

Polls the agent's console buffer, detects permission prompts via
pattern matching, creates ToolApproval records, and injects
approve/deny keystrokes when the user responds in the DuckDome UI.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from duckdome.wrapper.pattern_matcher import match_permission_prompt

if TYPE_CHECKING:
    from duckdome.services.tool_approval_service import ToolApprovalService

logger = logging.getLogger(__name__)


@dataclass
class _PendingPrompt:
    approval_id: str
    approve_key: str
    deny_key: str


def _read_console_buffer(pid: int, lines: int = 50) -> str:
    """Read the agent's console buffer via subprocess.

    Spawns console_reader.py in a separate process to avoid
    detaching the backend's console.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "duckdome.wrapper.console_reader",
             str(pid), str(lines)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except Exception:
        return ""


def _inject_response(pid: int, key: str, delay: float) -> bool:
    """Inject a single keystroke + Enter into the agent's console."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "duckdome.wrapper.injector_windows",
             str(pid), key, str(delay)],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        logger.exception("Failed to inject response for pid %d", pid)
        return False


class ConsoleMonitor:
    """Monitors an agent's console for permission prompts."""

    def __init__(
        self,
        pid: int,
        agent_type: str,
        channel_id: str,
        approval_service: ToolApprovalService,
        inject_delay: float = 0.05,
        poll_interval: float = 1.0,
    ) -> None:
        self._pid = pid
        self._agent_type = agent_type
        self._channel_id = channel_id
        self._approval_service = approval_service
        self._inject_delay = inject_delay
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seen: set[str] = set()
        self._pending: dict[str, _PendingPrompt] = {}
        self._last_buffer = ""
        self._poll_count = 0

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @channel_id.setter
    def channel_id(self, value: str) -> None:
        self._channel_id = value

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name=f"console-monitor-{self._agent_type}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        logger.info("[%s] console monitor started (pid=%d)",
                    self._agent_type, self._pid)
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                logger.exception("[%s] console monitor poll error",
                                 self._agent_type)
            self._stop.wait(self._poll_interval)
        logger.info("[%s] console monitor stopped", self._agent_type)

    def _poll_once(self) -> None:
        # 1. Read console buffer
        self._poll_count += 1
        buffer = _read_console_buffer(self._pid)
        if self._poll_count % 10 == 0:
            logger.info("[%s] monitor heartbeat: poll=%d buf_len=%d pending=%d seen=%d",
                        self._agent_type, self._poll_count, len(buffer), len(self._pending), len(self._seen))
        if not buffer:
            logger.warning("[%s] console buffer empty (pid=%d)", self._agent_type, self._pid)
            self._check_pending_resolutions()
            return

        changed = buffer != self._last_buffer
        if changed:
            preview = buffer[-300:].replace("\n", "\\n")
            logger.info("[%s] console buffer changed (pid=%d): ...%s", self._agent_type, self._pid, preview)
            self._last_buffer = buffer

        # 2. Always check for permission prompts (TUI apps redraw in place)
        match = match_permission_prompt(buffer, self._agent_type)
        if match and match.fingerprint not in self._seen:
            self._seen.add(match.fingerprint)
            logger.info("[%s] permission prompt detected: tool=%s desc=%s",
                        self._agent_type, match.tool, match.description)

            result = self._approval_service.request(
                agent=self._agent_type,
                tool=match.tool,
                arguments={"description": match.description}
                          if match.description else {},
                channel=self._channel_id,
            )

            if result.status == "pending" and result.approval:
                self._pending[result.approval.id] = _PendingPrompt(
                    approval_id=result.approval.id,
                    approve_key=match.approve_key,
                    deny_key=match.deny_key,
                )
            elif result.status == "approved":
                _inject_response(self._pid, match.approve_key,
                                 self._inject_delay)
            elif result.status == "denied":
                _inject_response(self._pid, match.deny_key,
                                 self._inject_delay)

        # 3. Check pending approvals for resolution
        self._check_pending_resolutions()

    def _check_pending_resolutions(self) -> None:
        resolved = []
        for approval_id, pending in self._pending.items():
            approval = self._approval_service.get(approval_id)
            if approval is None:
                resolved.append(approval_id)
                continue
            status = str(approval.status).lower()
            if status == "approved":
                logger.info("[%s] injecting approve for %s",
                            self._agent_type, approval.tool)
                _inject_response(self._pid, pending.approve_key,
                                 self._inject_delay)
                resolved.append(approval_id)
            elif status == "denied":
                logger.info("[%s] injecting deny for %s",
                            self._agent_type, approval.tool)
                _inject_response(self._pid, pending.deny_key,
                                 self._inject_delay)
                resolved.append(approval_id)
        for aid in resolved:
            del self._pending[aid]
