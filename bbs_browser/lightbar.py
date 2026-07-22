"""Lightbar menu — the one menu component for the entire browser.

Every selection menu in the program runs through this, so everything
feels the same: cursor up/down moves the bar, Enter selects, left/right
changes a value directly in the row, ESC/Q goes back. The numeric hotkeys
of classic BBS menus remain active at all times — whoever types instead
of navigating with the cursor gets to the same result. Without a real
terminal (pipe, test, CI) the component automatically falls back to
plain numeric input.
"""

import re
import sys

from . import keys
from .constants import BOLD, CLEAR, DIM, INVERT, RESET, screen_width
from .i18n import t

BACK = ""          # return value for "back"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
_LABEL_W = 22
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _plain_len(line):
    """Visible width of a line — color codes don't count."""
    return len(_ANSI_RE.sub("", line))


def index_of(rows, key):
    """Position of a key — so that a menu reopens with the bar on the
    same row after an action."""
    for i, row in enumerate(rows):
        if row[0] == key:
            return i
    return 0


def _rows_of(rows):
    return list(rows() if callable(rows) else rows)


def _fmt(key, label, value, width):
    if key is None:  # divider: plain heading, not selectable
        head = f"─[ {label} ]" if label else ""
        return head.ljust(width, "─")[:width]
    text = f"  [{key:>2}] {label:<{_LABEL_W}} {value}" if value else f"  [{key:>2}] {label}"
    return text[:width].ljust(width)


def _seek(data, idx, delta):
    """Next selectable row in the direction `delta` (skipping dividers)."""
    for _ in range(len(data)):
        idx = (idx + delta) % len(data)
        if data[idx][0] is not None:
            return idx
    return idx


def _seg(title, width):
    """Box heading in the classic style: ─[ TITLE ]──────"""
    head = f"─[ {title} ]" if title else ""
    return head[:width].ljust(width, "─")


def pane_lines(term, panes, titles, zone, sel):
    """The two side-by-side registers as a finished box.

    `panes` are the two row lists, `zone` is 1 (left) or 2 (right) and
    `sel` the selected index inside that pane."""
    width = screen_width()
    col_l = (width - 3) // 2
    col_r = width - 3 - col_l
    c = term.color
    out = [c + "┌" + _seg(titles[0], col_l) + "┬" + _seg(titles[1], col_r) + "┐" + RESET]

    def cell(rows, pos, cwidth, active):
        if pos >= len(rows):
            return " " * cwidth
        key, label, value = rows[pos]
        text = (f" [{key:>2}] {label}" if key is not None else f" {label}")[:cwidth].ljust(cwidth)
        if key is None:
            return DIM + text + RESET + c
        if active and pos == sel:
            return INVERT + text + RESET + c
        return text

    for pos in range(max(len(panes[0]), len(panes[1]))):
        out.append(c + "│" + cell(panes[0], pos, col_l, zone == 1)
                   + c + "│" + cell(panes[1], pos, col_r, zone == 2) + c + "│" + RESET)
    out.append(c + "└" + "─" * col_l + "┴" + "─" * col_r + "┘" + RESET)
    return out


def _hint(cycles):
    return t("lightbar.hint_cycle") if cycles else t("lightbar.hint_plain")


class _Screen:
    """The menu takes over the screen instead of appending at the bottom.

    Like on a real mailbox: clear once, draw starting at line 1 — and
    after that only ever overwrite its own lines. This keeps the bar
    flicker-free and the scrollback doesn't grow with every menu."""

    def __init__(self, clear=True):
        self.lines = 0
        self.clear = clear

    def draw(self, lines):
        if self.lines:
            sys.stdout.write(f"\x1b[{self.lines}A\x1b[J")
        elif self.clear:
            sys.stdout.write(CLEAR + HIDE_CURSOR)
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        self.lines = len(lines)

    def close(self):
        sys.stdout.write(SHOW_CURSOR + RESET)
        sys.stdout.flush()


def menu(term, title, rows, on_cycle=None, on_key=None, subtitle=None, page_size=0, start=0,
         hint=None, clear=True, header=None, panes=None, pane_titles=("", "")):
    """Shows a menu and returns the key of the selected row.

    `rows`     — list or function returning (key, label, value) tuples.
                 If a function, it is re-queried after every value change.
                 An entry with key=None is a divider (not selectable).
    `on_cycle` — optional: on_cycle(key, direction) changes the row's value
                 (direction -1/+1) and returns True if it handled it.
    `on_key`   — optional: on_key(key_pressed, key) for extra commands
                 (e.g. 'x' delete); returns True if the key was handled.
    `page_size`— visible rows for long lists (0 = all).
    `hint`     — custom footer instead of the standard help text.
    `clear`    — take over the screen (default) instead of appending below.
    `header`   — finished lines above the menu box (e.g. the intro banner);
                 headers too wide or too tall are dropped silently.
    `panes`    — optional (left_rows, right_rows): two registers drawn side
                 by side below the main list, in their own box. Left/right
                 switches between the two columns, up/down walks a column.
    Returns: the key of the row, or BACK ('') for back.
    """
    data = _rows_of(rows)
    panes = [list(panes[0]), list(panes[1])] if panes else None
    # A menu may consist of the two registers alone — but completely empty
    # it stays "back".
    if not data and not any(row[0] is not None for pane in (panes or []) for row in pane):
        return BACK
    if not keys.available():
        return _fallback(term, title, data, subtitle, panes, pane_titles)

    idx = index_of(data, start) if isinstance(start, str) else max(0, min(start, len(data) - 1))
    if data and data[idx][0] is None:
        idx = _seek(data, idx, 1)
    top = 0
    typed = ""
    # 0 = main list, 1 = left pane, 2 = right pane.
    zone = 0
    pidx = [0, 0]
    screen = _Screen(clear)
    width = screen_width() - 2
    view = page_size or len(data)
    # The header is dropped as soon as it no longer fits the terminal —
    # better no banner than a wrapped one.
    head = list(header or [])
    if any(_plain_len(line) > screen_width() for line in head):
        head = []

    def selectable(rows_):
        return any(row[0] is not None for row in rows_)

    def enter_pane(which, pos=0):
        """Move the bar into a pane — ignored when that column is empty."""
        nonlocal zone
        if not panes or not selectable(panes[which - 1]):
            return False
        zone = which
        rows_ = panes[which - 1]
        pidx[which - 1] = min(max(0, pos), len(rows_) - 1)
        if rows_[pidx[which - 1]][0] is None:
            pidx[which - 1] = _seek(rows_, pidx[which - 1], 1)
        return True

    # Without a main list the bar starts right in the registers.
    if not data and not enter_pane(1):
        enter_pane(2)

    def current():
        """The row the bar sits on, whichever zone that is."""
        if zone == 0:
            return data[idx]
        return panes[zone - 1][pidx[zone - 1]]

    def render():
        nonlocal top
        if idx < top:
            top = idx
        elif view and idx >= top + view:
            top = idx - view + 1
        c = term.color
        out = [c + line + RESET for line in head]
        out += [c + "╔" + "═" * (screen_width() - 2) + "╗" + RESET,
               c + "║ " + BOLD + title[:screen_width() - 4].ljust(screen_width() - 4) + RESET + c + " ║" + RESET]
        if subtitle:
            out.append(c + "║ " + DIM + subtitle[:screen_width() - 4].ljust(screen_width() - 4) + RESET + c + " ║" + RESET)
        out.append(c + "╚" + "═" * (screen_width() - 2) + "╝" + RESET)
        for pos in range(top, min(top + view, len(data))):
            key, label, value = data[pos]
            text = _fmt(key, label, value, width)
            if key is None:
                out.append(c + DIM + text + RESET)
            else:
                out.append(c + (INVERT + text if pos == idx and zone == 0 else text) + RESET)
        if len(data) > view:
            out.append(c + DIM + t("lightbar.more", shown=min(top + view, len(data)),
                                   total=len(data)) + RESET)
        if panes:
            out += pane_lines(term, panes, pane_titles, zone,
                               pidx[zone - 1] if zone else -1)
        out.append(c + DIM + "─" * screen_width() + RESET)
        foot = t("lightbar.typed", typed=typed) if typed else (hint or _hint(on_cycle))
        out.append(c + DIM + foot[:screen_width()] + RESET)
        screen.draw(out)

    def refresh():
        nonlocal data
        data = _rows_of(rows)

    interrupted = False
    try:
        with keys.raw_mode():
            render()
            while True:
                try:
                    key = keys.read_key()
                except KeyboardInterrupt:
                    # Ctrl+C in a menu behaves like at the prompt: it backs out
                    # of this screen and only hangs up on the second press.
                    interrupted = True
                    return BACK
                term.interrupts = 0  # a real keystroke breaks the hang-up streak
                if key in (keys.ESC, "q", "Q") or (key == keys.BACKSPACE and not typed):
                    return BACK
                if panes and key in (keys.UP, keys.DOWN, keys.LEFT, keys.RIGHT):
                    typed = ""
                    if zone == 0:
                        if key == keys.UP:
                            idx = _seek(data, idx, -1)
                        elif key == keys.DOWN:
                            # Past the last area the bar drops into the registers.
                            nxt = _seek(data, idx, 1)
                            if nxt <= idx and enter_pane(1):
                                pass
                            else:
                                idx = nxt
                        elif not (on_cycle and on_cycle(data[idx][0],
                                                        -1 if key == keys.LEFT else 1)):
                            if not enter_pane(1 if key == keys.LEFT else 2):
                                term.beep()
                        else:
                            refresh()
                            idx = min(idx, len(data) - 1)
                    else:
                        rows_ = panes[zone - 1]
                        cur = pidx[zone - 1]
                        if key == keys.UP:
                            nxt = _seek(rows_, cur, -1)
                            if nxt >= cur and data:  # wrapped: back up to the main list
                                zone = 0
                            else:
                                pidx[zone - 1] = nxt
                        elif key == keys.DOWN:
                            pidx[zone - 1] = _seek(rows_, cur, 1)
                        elif not enter_pane(2 if zone == 1 else 1, cur):
                            term.beep()
                elif key == keys.UP:
                    typed, idx = "", _seek(data, idx, -1)
                elif key == keys.DOWN:
                    typed, idx = "", _seek(data, idx, 1)
                elif key == keys.PGUP:
                    typed, idx, zone = "", _seek(data, max(0, idx - view) - 1, 1), 0
                elif key == keys.PGDN:
                    typed, idx, zone = "", _seek(data, min(len(data) - 1, idx + view) - 1, 1), 0
                elif key == keys.HOME:
                    typed, idx, zone = "", _seek(data, len(data) - 1, 1), 0
                elif key == keys.END:
                    typed, idx, zone = "", _seek(data, 0, -1), 0
                elif key in (keys.LEFT, keys.RIGHT):
                    typed = ""
                    if on_cycle and on_cycle(data[idx][0], -1 if key == keys.LEFT else 1):
                        refresh()
                        idx = min(idx, len(data) - 1)
                    else:
                        term.beep()
                elif key == keys.ENTER:
                    return current()[0]
                elif key == keys.BACKSPACE:
                    typed = typed[:-1]
                elif on_key and key and on_key(key, current()[0]):
                    typed = ""
                    refresh()
                    if not data:
                        return BACK
                    idx = min(idx, len(data) - 1)
                    if data[idx][0] is None:
                        idx = _seek(data, idx, 1)
                    zone = 0
                elif key and key.isprintable():
                    # Hotkeys as before: collect digits, go as soon as unambiguous.
                    # The registers take part: their keys ('1', 'h2') count too.
                    cand = typed + key
                    hits = [(z, i, row[0])
                            for z, rows_ in enumerate([data] + (panes or []))
                            for i, row in enumerate(rows_) if row[0] and row[0].startswith(cand)]
                    if not hits:
                        typed = ""
                        term.beep()
                    elif len(hits) == 1 and hits[0][2] == cand:
                        return hits[0][2]
                    else:
                        typed = cand
                        zone, pos, _ = hits[0]
                        if zone == 0:
                            idx = pos
                        else:
                            pidx[zone - 1] = pos
                render()
    finally:
        screen.close()
        # After the screen is restored, so the hint isn't overwritten.
        if interrupted:
            term.on_interrupt()


def _fallback(term, title, data, subtitle=None, panes=None, pane_titles=("", "")):
    """No controllable terminal: display classic numbered list and prompt."""
    term.box([title] + ([subtitle] if subtitle else []))

    def show(rows_):
        for key, label, value in rows_:
            if key is None:
                term.rule(label)
                continue
            print(term.color + f"  [{key:>2}] {label:<{_LABEL_W}}" + DIM + str(value) + RESET)

    show(data)
    for pane_title, rows_ in zip(pane_titles, panes or []):
        term.rule(pane_title)
        show(rows_)
    term.rule()
    return term.prompt(t("lightbar.prompt_choose")).strip()
