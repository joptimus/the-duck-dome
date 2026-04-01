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
