"""Matrix-Regen-Screensaver — 'sv' startet ihn, nach Leerlauf kommt er von selbst."""

import random
import shutil
import sys

from . import keys
from .colors import phosphor_rgb
from .constants import BOLD, RESET
from .i18n import t
from .rawscreen import cursor_to as _pos
from .rawscreen import raw_screen

GLYPHS = "abcdefghijklmnopqrstuvwxyz0123456789#$%&*+=<>:·"
HEAD = "\033[1;97m"          # hellweisser Tropfenkopf
FRAME_S = 0.07


def _rain_colors(term_color):
    """Tropfenkoerper und Auslauf im aktuellen Phosphor-Ton der App."""
    r, g, b = phosphor_rgb(term_color)
    body = f"\033[38;2;{r};{g};{b}m"
    tail = f"\033[38;2;{int(r * 0.35)};{int(g * 0.35)};{int(b * 0.35)}m"
    return body, tail


def matrix(term):
    """Matrix-Regen ueber den ganzen Schirm. Beliebige Taste (oder Ctrl+C) beendet."""
    if not sys.stdin.isatty():
        term.error(t("screensaver.tty_required"))
        return
    body_color, tail_color = _rain_colors(term.color)
    cols, rows = shutil.get_terminal_size((80, 24))
    max_trail = max(5, rows // 2)
    drops = [random.randint(-rows * 2, 0) for _ in range(cols)]
    trail = [random.randint(4, max_trail) for _ in range(cols)]
    try:
        with raw_screen():
            while True:
                out = []
                for x in range(cols):
                    y = drops[x]
                    if 1 <= y <= rows:
                        out.append(_pos(y, x + 1) + HEAD + random.choice(GLYPHS) + RESET)
                    if 1 <= y - 1 <= rows:
                        out.append(_pos(y - 1, x + 1) + body_color + random.choice(GLYPHS) + RESET)
                    mid = y - trail[x] // 2
                    if 1 <= mid <= rows:
                        out.append(_pos(mid, x + 1) + tail_color + random.choice(GLYPHS) + RESET)
                    end = y - trail[x]
                    if 1 <= end <= rows:
                        out.append(_pos(end, x + 1) + " ")
                    drops[x] += 1
                    if end > rows:
                        drops[x] = random.randint(-rows, 0)
                        trail[x] = random.randint(4, max_trail)
                sys.stdout.write("".join(out))
                sys.stdout.flush()
                if keys.wait_key(FRAME_S):
                    keys.read_char()
                    keys.drain()
                    break
    except KeyboardInterrupt:
        pass


def prompt_with_saver(term, label, idle_seconds):
    """Wie term.prompt, aber: passiert idle_seconds lang nichts, startet der
    Matrix-Regen. Ein Tastendruck beendet ihn und der Prompt kommt zurueck."""
    if not idle_seconds or not sys.stdin.isatty():
        return term.prompt(label)
    while True:
        term.skip = False
        sys.stdout.write(term.color + BOLD + label + RESET + term.color)
        sys.stdout.flush()
        try:
            if keys.wait_key(idle_seconds):
                text = input().strip()
                term.interrupts = 0
                return text
        except KeyboardInterrupt:
            term.on_interrupt()
            return ""
        finally:
            sys.stdout.write(RESET)
        print()
        matrix(term)
