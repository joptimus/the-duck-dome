"""Platform-aware keystroke injector.

Spawns injection in a SEPARATE process to avoid detaching the backend's console.
"""
from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def inject(text: str, pid: int, delay: float = 0.01) -> bool:
    """Inject text + Enter into the agent process's console.

    On Windows: spawns a helper subprocess that uses WriteConsoleInputW.
    On other platforms: raises NotImplementedError (tmux support TODO).
    """
    if sys.platform == "win32":
        return _inject_via_subprocess(text, pid, delay)
    else:
        raise NotImplementedError(
            "Keystroke injection not yet implemented for this platform. "
            "Future: tmux send-keys support."
        )


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
