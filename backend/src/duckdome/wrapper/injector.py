"""Platform-aware keystroke injector.

Spawns injection in a SEPARATE process to avoid detaching the backend's console.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


def inject(
    text: str,
    pid: int | None = None,
    delay: float = 0.01,
    *,
    tmux_session: str | None = None,
) -> bool:
    """Inject text + Enter into the agent process's console.

    On Windows: uses WriteConsoleInputW via a helper subprocess (requires pid).
    On Mac/Linux: uses tmux send-keys (requires tmux_session).
    """
    if sys.platform == "win32":
        if pid is None:
            logger.error("inject: pid required on Windows")
            return False
        return _inject_via_subprocess(text, pid, delay)
    else:
        if tmux_session is None:
            raise NotImplementedError(
                "Keystroke injection on Mac/Linux requires tmux_session parameter."
            )
        return _inject_via_tmux(text, tmux_session, delay)


def _inject_via_tmux(text: str, session_name: str, delay: float) -> bool:
    """Send text + Enter to a tmux pane via tmux send-keys."""
    # Always target the first pane in the session explicitly instead of relying
    # on the session's currently active pane. This avoids a race where text is
    # injected into one pane and Enter lands in another if focus changes.
    target = f"{session_name}:0.0"
    try:
        result = subprocess.run(
            ["tmux", "send-keys", "-t", target, "-l", text],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.error(
                "tmux send-keys failed (exit=%d): %s",
                result.returncode,
                result.stderr.decode("utf-8", errors="replace").strip(),
            )
            return False
        time.sleep(delay)
        enter_result = subprocess.run(
            ["tmux", "send-keys", "-t", target, "Enter"],
            capture_output=True,
        )
        if enter_result.returncode != 0:
            logger.error(
                "tmux send-keys Enter failed (exit=%d): %s",
                enter_result.returncode,
                enter_result.stderr.decode("utf-8", errors="replace").strip(),
            )
            return False
        return True
    except Exception:
        logger.exception("tmux injection failed for session %s", session_name)
        return False


def _inject_via_subprocess(text: str, pid: int, delay: float) -> bool:
    """Spawn a helper process to do the console injection.

    FreeConsole/AttachConsole are process-global — calling them from the
    backend process would detach uvicorn from its console and crash it.
    Running in a separate process avoids this entirely.
    """
    try:
        # Scale timeout to payload size: each keystroke takes ~delay seconds,
        # plus a fixed 10s buffer for subprocess startup and attach overhead.
        timeout = max(30, int(len(text) * delay) + 10)
        result = subprocess.run(
            [
                sys.executable, "-m", "duckdome.wrapper.injector_windows",
                str(pid), text, str(delay),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            logger.error(
                "Injection subprocess failed (exit=%d): %s",
                result.returncode, result.stderr.strip(),
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Injection subprocess timed out for pid %d", pid)
        return False
    except Exception:
        logger.exception("Failed to spawn injection subprocess for pid %d", pid)
        return False
