"""Win32 console buffer reader.

Reads the last N lines from a console process's screen buffer.
Must run as a SEPARATE process (AttachConsole is process-global).

Uses CreateFileW("CONOUT$") to get the real console screen buffer,
which works even when the process uses ConPTY (pseudo-console).

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
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = -1


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


# ReadConsoleOutputCharacterW takes COORD by value as a packed DWORD.
kernel32.ReadConsoleOutputCharacterW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.c_wchar_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,  # packed COORD
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
kernel32.ReadConsoleOutputCharacterW.restype = ctypes.wintypes.BOOL


def _pack_coord(x: int, y: int) -> ctypes.wintypes.DWORD:
    """Pack X,Y into a DWORD for ReadConsoleOutputCharacterW."""
    return ctypes.wintypes.DWORD((y & 0xFFFF) << 16 | (x & 0xFFFF))


def read_console(pid: int, lines: int = 50) -> str:
    """Read the last *lines* lines from the console of *pid*.

    Returns the text content. Trailing whitespace per line is stripped.
    """
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
        return ""

    handle = None
    try:
        # Open the real console screen buffer via CONOUT$.
        # GetStdHandle(-11) returns pipe handles under ConPTY which
        # don't support screen buffer APIs. CONOUT$ always works.
        handle = kernel32.CreateFileW(
            "CONOUT$", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None,
        )
        if handle == INVALID_HANDLE_VALUE or handle is None:
            return ""

        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            return ""

        width = info.dwSize.X
        buf_height = info.dwSize.Y
        if width == 0 or buf_height == 0:
            return ""

        # Read the full visible window.
        win_top = info.srWindow.Top
        win_bottom = info.srWindow.Bottom
        n_lines = min(win_bottom - win_top + 1, lines)
        start_y = max(0, win_bottom - n_lines + 1)
        total_chars = n_lines * width

        buf = ctypes.create_unicode_buffer(total_chars + 1)
        chars_read = ctypes.wintypes.DWORD(0)

        ok = kernel32.ReadConsoleOutputCharacterW(
            handle, buf, total_chars, _pack_coord(0, start_y),
            ctypes.byref(chars_read),
        )
        if not ok or chars_read.value == 0:
            return ""

        raw = buf.value
        result = []
        for i in range(n_lines):
            start = i * width
            end = min(start + width, len(raw))
            if start >= len(raw):
                break
            line = raw[start:end].rstrip()
            result.append(line)

        return "\n".join(result)
    finally:
        if handle is not None and handle != INVALID_HANDLE_VALUE:
            kernel32.CloseHandle(handle)
        kernel32.FreeConsole()
        kernel32.AttachConsole(ATTACH_PARENT_PROCESS)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pid> [lines]", file=sys.stderr)
        sys.exit(1)

    target_pid = int(sys.argv[1])
    num_lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    text = read_console(target_pid, num_lines)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    sys.exit(0)
