"""Platform-aware keystroke injector.

Dispatches to the appropriate platform implementation.
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def inject(text: str, pid: int, delay: float = 0.01) -> bool:
    """Inject text + Enter into the agent process's console.

    On Windows: uses WriteConsoleInputW.
    On other platforms: raises NotImplementedError (tmux support TODO).
    """
    if sys.platform == "win32":
        from duckdome.wrapper.injector_windows import inject as _win_inject
        return _win_inject(text, pid, delay)
    else:
        raise NotImplementedError(
            "Keystroke injection not yet implemented for this platform. "
            "Future: tmux send-keys support."
        )
