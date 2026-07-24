"""Shared raw-mode full-screen primitives for arcade games and the screensaver."""

import contextlib
import sys

from . import keys
from .constants import CLEAR, RESET

HIDE, SHOW = "\033[?25l", "\033[?25h"


def cursor_to(y, x):
    """ANSI sequence that moves the cursor to row y, column x (1-based)."""
    return f"\033[{y};{x}H"


@contextlib.contextmanager
def raw_screen():
    """Raw mode + blank screen without cursor — and everything cleanly restored."""
    sys.stdout.write(HIDE + CLEAR)
    try:
        with keys.raw_mode():
            yield
    finally:
        sys.stdout.write(RESET + SHOW + CLEAR)
        sys.stdout.flush()
