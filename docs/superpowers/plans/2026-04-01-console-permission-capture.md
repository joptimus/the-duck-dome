# Console Permission Capture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture agent CLI permission prompts from their console output, surface them as approval cards in the DuckDome chat UI, and inject approve/deny keystrokes back.

**Architecture:** A ConsoleMonitor thread per agent polls the console buffer via a ReadConsoleOutputW subprocess, pattern-matches permission prompts, creates ToolApproval records (reusing the existing approval service and UI), and injects y/n keystrokes when the user responds.

**Tech Stack:** Python, ctypes (Win32 ReadConsoleOutputCharacterW), existing ToolApprovalService, existing injector subprocess.

**Spec:** `docs/superpowers/specs/2026-04-01-console-permission-capture-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/duckdome/wrapper/console_reader.py` | Create | Win32 subprocess: AttachConsole + ReadConsoleOutputCharacterW, prints buffer text to stdout |
| `backend/src/duckdome/wrapper/pattern_matcher.py` | Create | Regex-based permission prompt detection per agent type |
| `backend/src/duckdome/wrapper/console_monitor.py` | Create | Per-agent polling thread: reads console, matches patterns, creates approvals, injects responses |
| `backend/src/duckdome/wrapper/manager.py` | Modify | Start/stop ConsoleMonitor on agent lifecycle |
| `backend/src/duckdome/services/wrapper_service.py` | Modify | Pass ToolApprovalService through to manager |
| `backend/src/duckdome/app.py` | Modify | Wire ToolApprovalService into WrapperService |
| `backend/tests/test_pattern_matcher.py` | Create | Unit tests for pattern matching |
| `backend/tests/test_console_monitor.py` | Create | Unit tests for monitor logic (mocked reader/injector) |

---

## Task 1: Console Reader Subprocess

The Win32 subprocess that reads the agent's console buffer. Same pattern as `injector_windows.py` — runs in a separate process because AttachConsole/FreeConsole are process-global.

**Files:**
- Create: `backend/src/duckdome/wrapper/console_reader.py`
- Test: Manual (requires a live console process)

- [ ] **Step 1: Create `console_reader.py`**

```python
"""Win32 console buffer reader.

Reads the last N lines from a console process's screen buffer.
Must run as a SEPARATE process (AttachConsole is process-global).

Usage:
    python -m duckdome.wrapper.console_reader <pid> [lines]
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

if sys.platform != "win32":
    raise ImportError("console_reader is only available on Windows")

kernel32 = ctypes.windll.kernel32

ATTACH_PARENT_PROCESS = 0xFFFFFFFF


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.wintypes.SHORT), ("Y", ctypes.wintypes.SHORT)]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.wintypes.SHORT),
        ("Top", ctypes.wintypes.SHORT),
        ("Right", ctypes.wintypes.SHORT),
        ("Bottom", ctypes.wintypes.SHORT),
    ]


class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD),
        ("dwCursorPosition", COORD),
        ("wAttributes", ctypes.wintypes.WORD),
        ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD),
    ]


def read_console(pid: int, lines: int = 50) -> str:
    """Read the last *lines* lines from the console of *pid*.

    Returns the text content. Trailing whitespace per line is stripped.
    """
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
        return ""

    try:
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle is None or handle == -1:
            return ""

        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            return ""

        width = info.dwSize.X
        cursor_y = info.dwCursorPosition.Y

        # Read from (cursor_y - lines) up to cursor_y
        start_y = max(0, cursor_y - lines + 1)
        n_lines = cursor_y - start_y + 1
        total_chars = n_lines * width

        buf = ctypes.create_unicode_buffer(total_chars)
        chars_read = ctypes.wintypes.DWORD(0)
        origin = COORD(X=0, Y=start_y)

        kernel32.ReadConsoleOutputCharacterW(
            handle, buf, total_chars, origin, ctypes.byref(chars_read),
        )

        # Split into lines and strip trailing whitespace
        raw = buf.value
        result = []
        for i in range(n_lines):
            line = raw[i * width : (i + 1) * width].rstrip()
            result.append(line)

        return "\n".join(result)
    finally:
        kernel32.FreeConsole()
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pid> [lines]", file=sys.stderr)
        sys.exit(1)

    target_pid = int(sys.argv[1])
    num_lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    text = read_console(target_pid, num_lines)
    print(text)
    sys.exit(0)
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/duckdome/wrapper/console_reader.py
git commit -m "feat: add Win32 console buffer reader subprocess"
```

---

## Task 2: Pattern Matcher

Regex-based detection of permission prompts per agent type.

**Files:**
- Create: `backend/src/duckdome/wrapper/pattern_matcher.py`
- Create: `backend/tests/test_pattern_matcher.py`

- [ ] **Step 1: Write failing tests for pattern matcher**

```python
"""Tests for pattern_matcher module."""
import pytest

from duckdome.wrapper.pattern_matcher import match_permission_prompt, PromptMatch


class TestClaudePatterns:
    """Test Claude Code permission prompt detection."""

    def test_bash_tool_prompt(self):
        text = (
            "  ❯ Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Bash"
        assert "git status" in match.description
        assert match.approve_key == "y"
        assert match.deny_key == "n"

    def test_read_tool_prompt(self):
        text = (
            "  ❯ Do you want to allow Claude to use Read?\n"
            "    File: /home/user/project/main.py\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Read"
        assert "main.py" in match.description

    def test_edit_tool_prompt(self):
        text = (
            "  ❯ Do you want to allow Claude to use Edit?\n"
            "    File: src/app.py\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Edit"

    def test_no_match_on_regular_output(self):
        text = "Hello, I can help you with that.\nLet me read the file."
        match = match_permission_prompt(text, "claude")
        assert match is None

    def test_no_match_on_empty(self):
        match = match_permission_prompt("", "claude")
        assert match is None

    def test_fingerprint_is_stable(self):
        text = (
            "  ❯ Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        m1 = match_permission_prompt(text, "claude")
        m2 = match_permission_prompt(text, "claude")
        assert m1.fingerprint == m2.fingerprint

    def test_different_commands_different_fingerprints(self):
        text1 = (
            "  ❯ Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        text2 = (
            "  ❯ Do you want to allow Claude to use Bash?\n"
            "    Command: git commit\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        m1 = match_permission_prompt(text1, "claude")
        m2 = match_permission_prompt(text2, "claude")
        assert m1.fingerprint != m2.fingerprint

    def test_unknown_agent_returns_none(self):
        text = (
            "  ❯ Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "unknown_agent")
        assert match is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_pattern_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'duckdome.wrapper.pattern_matcher'`

- [ ] **Step 3: Implement `pattern_matcher.py`**

```python
"""Permission prompt pattern matching per agent type."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptMatch:
    tool: str
    description: str
    approve_key: str
    deny_key: str
    fingerprint: str


def _fingerprint(tool: str, description: str) -> str:
    raw = f"{tool}:{description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# Claude Code patterns.
# Example prompt:
#   ❯ Do you want to allow Claude to use Bash?
#     Command: git status
#     (Y)es | (N)o | Yes, and don't ask again for this tool
_CLAUDE_TOOL_RE = re.compile(
    r"allow Claude to use (\w+)\?",
    re.IGNORECASE,
)

# Description lines appear between the tool line and the (Y)es|(N)o line.
# Common prefixes: "Command:", "File:", or just indented text.
_CLAUDE_DESC_RE = re.compile(
    r"^\s+(?:Command|File|Path|Description):\s*(.+)",
    re.MULTILINE,
)

_CLAUDE_YN_RE = re.compile(r"\(Y\)es\s*\|\s*\(N\)o", re.IGNORECASE)


def _match_claude(text: str) -> PromptMatch | None:
    tool_m = _CLAUDE_TOOL_RE.search(text)
    if not tool_m:
        return None

    yn_m = _CLAUDE_YN_RE.search(text)
    if not yn_m:
        return None

    tool = tool_m.group(1)

    desc_m = _CLAUDE_DESC_RE.search(text)
    description = desc_m.group(1).strip() if desc_m else ""

    return PromptMatch(
        tool=tool,
        description=description,
        approve_key="y",
        deny_key="n",
        fingerprint=_fingerprint(tool, description),
    )


_MATCHERS: dict[str, callable] = {
    "claude": _match_claude,
}


def match_permission_prompt(text: str, agent_type: str) -> PromptMatch | None:
    """Match a permission prompt in *text* for the given *agent_type*.

    Returns a PromptMatch if found, None otherwise.
    """
    matcher = _MATCHERS.get(agent_type)
    if matcher is None:
        return None
    return matcher(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_pattern_matcher.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/duckdome/wrapper/pattern_matcher.py backend/tests/test_pattern_matcher.py
git commit -m "feat: add permission prompt pattern matcher with Claude patterns"
```

---

## Task 3: Console Monitor

The per-agent polling thread that ties everything together: reads console, matches patterns, creates approvals, injects responses.

**Files:**
- Create: `backend/src/duckdome/wrapper/console_monitor.py`
- Create: `backend/tests/test_console_monitor.py`

- [ ] **Step 1: Write failing tests for console monitor**

```python
"""Tests for console_monitor module."""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from duckdome.wrapper.console_monitor import ConsoleMonitor
from duckdome.wrapper.pattern_matcher import PromptMatch
from duckdome.models.tool_approval import ToolApproval, ToolApprovalStatus


class TestConsoleMonitor:

    def _make_monitor(self, **overrides):
        defaults = dict(
            pid=1234,
            agent_type="claude",
            channel_id="test-channel",
            approval_service=MagicMock(),
            inject_delay=0.05,
            poll_interval=0.1,
        )
        defaults.update(overrides)
        return ConsoleMonitor(**defaults)

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_detects_permission_prompt_and_creates_approval(self, mock_read):
        """When a permission prompt appears, an approval is created."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        svc = MagicMock()
        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={"command": "git status"},
            channel="test-channel",
        )
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        svc.request.assert_called_once()
        call_kwargs = svc.request.call_args.kwargs
        assert call_kwargs["tool"] == "Bash"
        assert call_kwargs["agent"] == "claude"
        assert call_kwargs["channel"] == "test-channel"

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_does_not_duplicate_same_prompt(self, mock_read):
        """Same prompt appearing twice only creates one approval."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        svc = MagicMock()
        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()
        monitor._poll_once()

        assert svc.request.call_count == 1

    @patch("duckdome.wrapper.console_monitor._inject_response")
    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_injects_y_on_approval(self, mock_read, mock_inject):
        """When approval is resolved as approved, inject 'y' + Enter."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc = MagicMock()
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )
        svc.get.return_value = approval

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()  # detect prompt, create approval

        # Simulate user approving
        approval.status = ToolApprovalStatus.APPROVED
        monitor._poll_once()  # check resolution, inject

        mock_inject.assert_called_once_with(1234, "y", 0.05)

    @patch("duckdome.wrapper.console_monitor._inject_response")
    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_injects_n_on_denial(self, mock_read, mock_inject):
        """When approval is resolved as denied, inject 'n' + Enter."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc = MagicMock()
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )
        svc.get.return_value = approval

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        approval.status = ToolApprovalStatus.DENIED
        monitor._poll_once()

        mock_inject.assert_called_once_with(1234, "n", 0.05)

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_no_match_does_nothing(self, mock_read):
        """Regular output does not create approvals."""
        mock_read.return_value = "Hello world\nProcessing files..."

        svc = MagicMock()
        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        svc.request.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_console_monitor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `console_monitor.py`**

```python
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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from duckdome.wrapper.pattern_matcher import PromptMatch, match_permission_prompt

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
        buffer = _read_console_buffer(self._pid)
        if not buffer or buffer == self._last_buffer:
            self._check_pending_resolutions()
            return
        self._last_buffer = buffer

        # 2. Check for permission prompts
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_console_monitor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/duckdome/wrapper/console_monitor.py backend/tests/test_console_monitor.py
git commit -m "feat: add console monitor for permission prompt capture"
```

---

## Task 4: Wire into Manager and App

Connect the ConsoleMonitor to the agent lifecycle.

**Files:**
- Modify: `backend/src/duckdome/wrapper/manager.py:242-258` (AgentProcess dataclass)
- Modify: `backend/src/duckdome/wrapper/manager.py:260-277` (AgentProcessManager.__init__)
- Modify: `backend/src/duckdome/wrapper/manager.py:364-383` (_start_agent_inner, after Popen)
- Modify: `backend/src/duckdome/services/wrapper_service.py:17-25` (constructor)
- Modify: `backend/src/duckdome/app.py:116` (WrapperService init)

- [ ] **Step 1: Add `console_monitor` field to `AgentProcess`**

In `manager.py`, add to the `AgentProcess` dataclass (after line 257):

```python
from duckdome.wrapper.console_monitor import ConsoleMonitor

@dataclass
class AgentProcess:
    # ... existing fields ...
    console_monitor: ConsoleMonitor | None = None
```

Add the import at the top of manager.py alongside the other wrapper imports.

- [ ] **Step 2: Add `tool_approval_service` to `AgentProcessManager.__init__`**

The manager needs access to the approval service to pass to monitors.

```python
class AgentProcessManager:
    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        mcp_host: str = "127.0.0.1",
        app_port: int = 8000,
        tool_approval_service=None,
    ) -> None:
        # ... existing init ...
        self._tool_approval_service = tool_approval_service
```

- [ ] **Step 3: Start ConsoleMonitor after Popen in `_start_agent_inner`**

In `_start_agent_inner`, after `agent_proc.pid = proc.pid` (around line 382), add:

```python
# Start console monitor for permission prompt capture (Windows only)
if sys.platform == "win32" and self._tool_approval_service is not None:
    monitor = ConsoleMonitor(
        pid=agent_proc.pid,
        agent_type=agent_type,
        channel_id=agent_proc.active_channel,
        approval_service=self._tool_approval_service,
        inject_delay=agent_proc.inject_delay,
    )
    agent_proc.console_monitor = monitor
    monitor.start()
```

- [ ] **Step 4: Stop ConsoleMonitor in `stop_agent`**

Find the `stop_agent` method. Before killing the process, add:

```python
if agent_proc.console_monitor:
    agent_proc.console_monitor.stop()
```

- [ ] **Step 5: Update channel_id on trigger**

In `_queue_watcher`, after `agent_proc.active_channel = str(channel).strip() or "general"` (line 701), add:

```python
if agent_proc.console_monitor:
    agent_proc.console_monitor.channel_id = agent_proc.active_channel
```

- [ ] **Step 6: Pass `tool_approval_service` through WrapperService**

In `wrapper_service.py`:

```python
class WrapperService:
    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        tool_approval_service=None,
    ) -> None:
        self._manager = AgentProcessManager(
            data_dir=data_dir,
            mcp_port=mcp_port,
            tool_approval_service=tool_approval_service,
        )
```

- [ ] **Step 7: Wire in `app.py`**

In `app.py`, change the WrapperService init (around line 116):

```python
wrapper_service = WrapperService(
    data_dir=data_dir,
    tool_approval_service=tool_approval_service,
)
```

- [ ] **Step 8: Run existing tests to verify nothing broke**

Run: `cd backend && python -m pytest tests/test_wrapper_manager.py tests/test_tool_approvals.py -v`
Expected: All PASS (existing tests should not break since `tool_approval_service` defaults to `None`)

- [ ] **Step 9: Commit**

```bash
git add backend/src/duckdome/wrapper/manager.py backend/src/duckdome/services/wrapper_service.py backend/src/duckdome/app.py
git commit -m "feat: wire console monitor into agent lifecycle"
```

---

## Task 5: Manual Integration Test

Verify the full flow end-to-end with a live Claude agent.

- [ ] **Step 1: Start the app**

Run: `npm run dev` (or however the app is started)

- [ ] **Step 2: Trigger Claude in a channel**

Send a message that will cause Claude to use a tool requiring permission (e.g., "Run `git status` and tell me the output").

- [ ] **Step 3: Observe the backend logs**

Look for:
```
[claude] console monitor started (pid=XXXXX)
[claude] permission prompt detected: tool=Bash desc=git status
[ToolApproval] broadcasting: id=... tool=Bash agent=claude ...
```

- [ ] **Step 4: Check the UI**

Verify the approval card appears in the chat timeline.

- [ ] **Step 5: Click approve**

Verify the backend logs show:
```
[claude] injecting approve for Bash
```

And Claude proceeds with the tool execution.

- [ ] **Step 6: Tune patterns if needed**

If the regex doesn't match Claude's actual output, update `pattern_matcher.py` with the real format. The console reader output will show exactly what Claude prints. Commit any pattern fixes.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Console reader subprocess | `console_reader.py` |
| 2 | Pattern matcher + tests | `pattern_matcher.py`, `test_pattern_matcher.py` |
| 3 | Console monitor + tests | `console_monitor.py`, `test_console_monitor.py` |
| 4 | Wire into manager and app | `manager.py`, `wrapper_service.py`, `app.py` |
| 5 | Manual integration test | No code changes — verify + tune |
