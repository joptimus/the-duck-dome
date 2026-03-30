"""Win32 keystroke injection into agent console processes.

Ported from agentchattr/apps/server/src/wrapper_windows.py.
Uses WriteConsoleInputW to inject text character-by-character
followed by an Enter keystroke into a console process.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys
import threading
import time

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    raise ImportError("injector_windows is only available on Windows")

kernel32 = ctypes.windll.kernel32

# Constants
KEY_EVENT = 0x0001
ATTACH_PARENT_PROCESS = 0xFFFFFFFF


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.wintypes.BOOL),
        ("wRepeatCount", ctypes.wintypes.WORD),
        ("wVirtualKeyCode", ctypes.wintypes.WORD),
        ("wVirtualScanCode", ctypes.wintypes.WORD),
        ("UnicodeChar", ctypes.c_wchar),
        ("dwControlKeyState", ctypes.wintypes.DWORD),
    ]


class INPUT_RECORD_UNION(ctypes.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD)]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventType", ctypes.wintypes.WORD),
        ("Event", INPUT_RECORD_UNION),
    ]


def _make_key_event(char: str, key_down: bool) -> INPUT_RECORD:
    rec = INPUT_RECORD()
    rec.EventType = KEY_EVENT
    rec.Event.KeyEvent.bKeyDown = key_down
    rec.Event.KeyEvent.wRepeatCount = 1
    rec.Event.KeyEvent.wVirtualKeyCode = 0
    rec.Event.KeyEvent.wVirtualScanCode = 0
    rec.Event.KeyEvent.UnicodeChar = char
    rec.Event.KeyEvent.dwControlKeyState = 0
    return rec


# Process-level lock: FreeConsole/AttachConsole are process-global operations.
# Only one thread may perform console injection at a time.
_console_lock = threading.Lock()


def inject(text: str, pid: int, delay: float = 0.01) -> bool:
    """Inject text + Enter into the console of the given PID.

    Returns True on success, False on failure.
    Thread-safe: serialized via _console_lock since console attachment is process-global.
    """
    with _console_lock:
        return _inject_impl(text, pid, delay)


def _inject_impl(text: str, pid: int, delay: float) -> bool:
    # Free our own console first, then attach to the target process
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        logger.error("AttachConsole(%d) failed", pid)
        # Re-attach to our own console
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
        return False

    try:
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        if handle is None or handle == -1:
            logger.error("GetStdHandle failed for pid %d", pid)
            return False

        written = ctypes.wintypes.DWORD(0)

        for char in text:
            down = _make_key_event(char, True)
            up = _make_key_event(char, False)
            records = (INPUT_RECORD * 2)(down, up)
            kernel32.WriteConsoleInputW(handle, records, 2, ctypes.byref(written))
            if delay > 0:
                time.sleep(delay)

        # Press Enter
        enter_down = _make_key_event("\r", True)
        enter_up = _make_key_event("\r", False)
        records = (INPUT_RECORD * 2)(enter_down, enter_up)
        kernel32.WriteConsoleInputW(handle, records, 2, ctypes.byref(written))

        return True
    finally:
        kernel32.FreeConsole()
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
