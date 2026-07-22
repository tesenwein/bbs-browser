"""Raw keyboard input: arrow keys, Enter, ESC — the basis of the lightbar.

Real ANSI mailboxes (Renegade, Mystic, Telegard) offered lightbar menus
operated via cursor keys, alongside the hotkeys. For that, the terminal
must deliver characters one at a time instead of line by line — on POSIX
via termios/cbreak, on Windows via msvcrt. If neither is available (pipe,
CI, dumb terminal), `available()` reports False and menus fall back to
numeric input.
"""

import contextlib
import os
import sys
import time

UP, DOWN, LEFT, RIGHT = "UP", "DOWN", "LEFT", "RIGHT"
HOME, END, PGUP, PGDN = "HOME", "END", "PGUP", "PGDN"
ENTER, ESC, BACKSPACE, TAB = "ENTER", "ESC", "BACKSPACE", "TAB"

try:  # POSIX
    import select
    import termios
    import tty
except ImportError:  # pragma: no cover - Windows only
    select = termios = tty = None

try:  # Windows
    import msvcrt
except ImportError:
    msvcrt = None

# How often the Windows path checks for a keystroke while waiting.
POLL_S = 0.02

# ESC sequences as sent by ANSI-BBS/VT100 terminals.
_CSI = {
    "A": UP, "B": DOWN, "C": RIGHT, "D": LEFT,
    "H": HOME, "F": END,
    "1~": HOME, "4~": END, "5~": PGUP, "6~": PGDN, "7~": HOME, "8~": END,
}
_WIN = {
    "H": UP, "P": DOWN, "M": RIGHT, "K": LEFT,
    "G": HOME, "O": END, "I": PGUP, "Q": PGDN,
}


def init_console():
    """Make the Windows console behave like a real ANSI terminal.

    Two things are off by default there: the classic console swallows ANSI
    escapes unless ENABLE_VIRTUAL_TERMINAL_PROCESSING is set, and stdout runs
    on a legacy codepage that cannot encode the box-drawing characters the
    boards are built from. On POSIX only the lenient stdin decoding applies."""
    # Everywhere: a stray non-UTF-8 byte at the prompt (broken paste, terminal
    # still recovering from raw mode) must not kill input() with a
    # UnicodeDecodeError -- decode it to U+FFFD instead.
    with contextlib.suppress(AttributeError, ValueError, OSError):
        sys.stdin.reconfigure(errors="replace")
    if msvcrt is None:
        return
    for stream in (sys.stdin, sys.stdout, sys.stderr):  # pragma: no cover - Windows
        with contextlib.suppress(AttributeError, ValueError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    with contextlib.suppress(Exception):  # pragma: no cover - Windows
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle in (-11, -12):  # STDOUT, STDERR
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(kernel32.GetStdHandle(handle), ctypes.byref(mode)):
                kernel32.SetConsoleMode(
                    kernel32.GetStdHandle(handle), mode.value | 0x0004
                )


def available():
    """Can this session read individual keys at all?"""
    if os.environ.get("BBS_NO_LIGHTBAR"):
        return False
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False
    except (AttributeError, ValueError):
        return False
    return bool(termios or msvcrt)


class raw_mode:
    """Context manager: puts the terminal into cbreak mode for the menu's duration.

    ISIG is switched off along the way: otherwise Ctrl+C would fire a SIGINT
    at an arbitrary point in the drawing loop and tear the whole session down.
    Off, it arrives as a plain \\x03 character — the readers below turn it into
    something the screen in question can handle (back out, quit the game),
    exactly like at the line prompt."""

    def __init__(self):
        self._fd = None
        self._saved = None

    def __enter__(self):
        if termios and sys.stdin.isatty():
            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            mode = termios.tcgetattr(self._fd)
            mode[3] &= ~termios.ISIG  # lflag
            termios.tcsetattr(self._fd, termios.TCSANOW, mode)
        return self

    def __exit__(self, *exc):
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        return False


def _getch():
    """A character straight from the terminal — bypassing Python's line buffer.

    sys.stdin.read() would buffer and thereby blind select(); in raw mode
    reading must happen on the file descriptor directly."""
    fd = sys.stdin.fileno()
    data = os.read(fd, 1)
    if not data:
        return ""
    # Collect a multi-byte (UTF-8) character in full.
    while data[0] >= 0x80 and len(data) < 4:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            data += os.read(fd, 1)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def wait_key(timeout=0.0):
    """True as soon as a keystroke is pending — waits at most timeout seconds.

    On Windows select() only works on sockets, never on stdin (WinError
    10038), so there we poll msvcrt.kbhit() instead."""
    if msvcrt is not None:
        deadline = time.monotonic() + timeout
        while True:
            if msvcrt.kbhit():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(POLL_S, remaining))
    return bool(select.select([sys.stdin.fileno()], [], [], timeout)[0])


def read_char():
    """One raw character — the platform-neutral counterpart to wait_key()."""
    if msvcrt is not None:
        return msvcrt.getwch()
    return _getch()


def drain():
    """Swallow anything still pending (e.g. the tail of an escape sequence)."""
    while wait_key(0):
        read_char()


def _peek(timeout=0.05):
    """The next character, if it arrives within the deadline."""
    return _getch() if wait_key(timeout) else ""


def _read_escape():
    """Reads the rest of an ESC sequence — or reports a bare ESC."""
    peek = _peek
    second = peek()
    if second not in ("[", "O"):
        return ESC  # bare ESC (or Alt+key — treated as ESC here)
    seq = ""
    for _ in range(4):
        ch = peek()
        if not ch:
            break
        seq += ch
        if ch.isalpha() or ch == "~":
            break
    return _CSI.get(seq, _CSI.get(seq[-1:], ESC))


def read_key():
    """Returns a keypress as a name (UP, ENTER, ...) or as a character.

    Must be called within `raw_mode()`. Ctrl+C is reported as a
    KeyboardInterrupt — raised right here, at a defined point, because
    raw_mode() has switched the signal off. The caller decides what happens
    (the lightbar backs out and asks, like the prompt does).
    """
    if msvcrt and not termios:  # pragma: no cover - Windows path
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return _WIN.get(msvcrt.getwch(), "")
        if ch == "\x03":
            raise KeyboardInterrupt
        return {"\r": ENTER, "\n": ENTER, "\x1b": ESC, "\x08": BACKSPACE, "\t": TAB}.get(ch, ch)

    ch = _getch()
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x04":  # Ctrl+D — like ESC/back
        return ESC
    if ch == "\x1b":
        return _read_escape()
    return {"\r": ENTER, "\n": ENTER, "\x7f": BACKSPACE, "\x08": BACKSPACE, "\t": TAB}.get(ch, ch)


_ARROWS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}
# Scancodes the arrow keys send after the \x00/\xe0 prefix on Windows.
_WIN_ARROWS = {"H": "up", "P": "down", "M": "right", "K": "left"}


def read_game_key(timeout):
    """A key for the arcade loop: 'up'/'down'/'left'/'right', 'esc',
    the lowercase character — or "" if nothing arrived within timeout.

    Ctrl+C counts as 'q': it leaves the game instead of dropping the call.

    Non-blocking by design: the games need a frame clock, not a prompt."""
    if not wait_key(timeout):
        return ""
    if msvcrt is not None:  # pragma: no cover - Windows path
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return _WIN_ARROWS.get(msvcrt.getwch(), "esc")
        if ch == "\x03":
            return "q"
        return "esc" if ch == "\x1b" else ch.lower()

    # Read from the fd directly: sys.stdin.read() would buffer internally and
    # leave keystrokes sitting invisibly, so the next arrow key would deliver
    # the tail end of the previous sequence.
    data = os.read(sys.stdin.fileno(), 64).decode("utf-8", "ignore")
    if not data:
        return ""
    # With a held key, sequences pile up — the most recent one counts.
    last = data.rsplit("\x1b", 1)
    if len(last) == 2 and last[1][:1] == "[":
        # Arrived split up? Wait briefly for the rest of the sequence.
        if len(last[1]) < 2 and wait_key(0.02):
            last[1] += os.read(sys.stdin.fileno(), 8).decode("utf-8", "ignore")
        return _ARROWS.get(last[1][:2], "esc")
    if data[0] == "\x1b":
        return "esc"
    if "\x03" in data:
        return "q"
    return data[-1].lower()
