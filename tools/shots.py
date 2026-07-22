#!/usr/bin/env python3
"""Screenshot tool: drives the BBS browser through a pseudo-terminal,
emulates the screen with pyte, and writes it out as a PNG to docs/screenshots/.

Usage:  python3 tools/shots.py [name ...]     (no argument: all scenes)

Rendering uses Menlo on a fixed character grid — only that way do the
CP437 borders (═ ║ ╔) and block graphics (█) sit flush against each other.
An SVG with a system font won't do: if the viewer lacks the border glyphs,
the whole layout collapses into fallback boxes.

Requires `pyte` (development only):  pip install pyte
"""

import json
import os
import pty
import select
import shutil
import signal
import sys
import tempfile
import time

import pyte

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")

COLS, ROWS = 84, 46

# --- Appearance of the rendered "screen" -----------------------------------
# (file, index) pairs for regular and bold. The first entry whose files
# exist wins — macOS first, then the usual Linux monospace fonts. All that
# matters is that the font knows box-drawing (U+2500…) and block graphics
# (U+2580…); Ubuntu Mono, for instance, lacks the half-block ▀ and is
# therefore excluded.
FONT_CANDIDATES = [
    (("/System/Library/Fonts/Menlo.ttc", 0), ("/System/Library/Fonts/Menlo.ttc", 1)),
    (("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
     ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0)),
    (("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 0),
     ("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 0)),
    (("/usr/share/fonts/truetype/freefont/FreeMono.ttf", 0),
     ("/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf", 0)),
]
FONT_SIZE = 40          # 2x resolution, so the PNG stays sharp when scaled
PAD = 44

# Menlo's bold face has no box-drawing/block glyphs (U+2500-259F) — PIL
# silently falls back to tofu boxes for them. These characters carry no
# meaningful weight anyway, so always draw them with the regular face.
NO_BOLD_RANGES = ((0x2500, 0x257F), (0x2580, 0x259F))


def _is_line_art(char):
    cp = ord(char)
    return any(lo <= cp <= hi for lo, hi in NO_BOLD_RANGES)
BG = (12, 11, 9)
DEFAULT_FG = (255, 182, 66)

# pyte gives basic colors as names, 256-colors as hex without '#'.
NAMED = {
    "black": (26, 26, 26), "red": (195, 64, 67), "green": (78, 201, 176),
    "brown": (215, 166, 95), "blue": (92, 156, 245), "magenta": (198, 120, 221),
    "cyan": (78, 201, 208), "white": (232, 230, 227),
    "brightblack": (90, 90, 90), "brightred": (224, 108, 117),
    "brightgreen": (126, 231, 135), "brightbrown": (229, 192, 123),
    "brightblue": (121, 184, 255), "brightmagenta": (210, 168, 255),
    "brightcyan": (118, 227, 234), "brightwhite": (255, 255, 255),
}


def _color(value, fallback):
    if not value or value == "default":
        return fallback
    if value in NAMED:
        return NAMED[value]
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return fallback


def _load_fonts():
    """First available font pair (regular, bold) from FONT_CANDIDATES."""
    from PIL import ImageFont

    for reg, bld in FONT_CANDIDATES:
        if os.path.exists(reg[0]) and os.path.exists(bld[0]):
            return (ImageFont.truetype(reg[0], FONT_SIZE, index=reg[1]),
                    ImageFont.truetype(bld[0], FONT_SIZE, index=bld[1]))
    raise SystemExit("no suitable monospace font found — "
                     "see FONT_CANDIDATES in tools/shots.py")


def render_png(screen, path):
    """Draw the emulated screen as a PNG — cell by cell on the grid."""
    from PIL import Image, ImageDraw

    regular, bold = _load_fonts()

    # Cell dimensions taken directly from the font metrics: this makes box
    # drawing and block graphics tile exactly, both horizontally and vertically.
    cell_w = round(regular.getlength("M"))
    ascent, descent = regular.getmetrics()
    cell_h = ascent + descent

    # Trim empty rows at the end — the screen is generously sized, but the
    # image should only show the part that's actually used.
    used = 0
    for y in range(ROWS):
        row = screen.buffer[y]
        if any((row[x].data or " ").strip() for x in range(COLS)):
            used = y + 1
    rows = min(ROWS, used + 1)

    w = COLS * cell_w + 2 * PAD
    h = rows * cell_h + 2 * PAD
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    for y in range(rows):
        row = screen.buffer[y]
        for x in range(COLS):
            ch = row[x]
            char = ch.data or " "
            fg = _color(ch.fg, DEFAULT_FG)
            bg = _color(ch.bg, None)
            if ch.reverse:
                fg, bg = BG, (fg or DEFAULT_FG)
            px, py = PAD + x * cell_w, PAD + y * cell_h
            if bg:
                draw.rectangle([px, py, px + cell_w - 1, py + cell_h - 1], fill=bg)
            if char.strip():
                use_bold = ch.bold and len(char) == 1 and not _is_line_art(char)
                draw.text((px, py), char, font=(bold if use_bold else regular),
                          fill=fg, anchor="la")

    # Subtle scanlines — CRT-monitor feel without swallowing the text.
    scan = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scan)
    for y in range(0, h, 4):
        sdraw.rectangle([0, y, w, y + 1], fill=(0, 0, 0, 28))
    img = Image.alpha_composite(img.convert("RGBA"), scan).convert("RGB")

    img.save(path, optimize=True)
    return img.size


def _seed_home(home, profile=None, state=None):
    """Fresh HOME with a prepared profile — no registration dialog, a
    populated main menu, and guaranteed no real user data."""
    data = {
        "profile": {
            "handle": "THEO",
            "caller_count": 1987,
            "last_call": "19.07.2026 23:14",
        },
        "ui": {"fast": True, "images": True, "baud": 0, "sound": False, "lang": "en"},
        "bookmarks": [
            {"url": "https://heise.de", "title": "heise online"},
            {"url": "https://lobste.rs", "title": "Lobsters"},
            {"url": "gopher://gopher.floodgap.com", "title": "Floodgap Gopher"},
            {"url": "gemini://geminiprotocol.net", "title": "Gemini Protocol"},
        ],
        "history": [
            {"url": "https://en.wikipedia.org/wiki/Bulletin_board_system", "title": "Bulletin board system"},
            {"url": "https://lobste.rs", "title": "Lobsters"},
            {"url": "https://heise.de", "title": "heise online"},
        ],
    }
    if profile:
        data["profile"].update(profile)
    if state:
        for key, value in state.items():
            data.setdefault(key, {})
            data[key] = {**data.get(key, {}), **value} if isinstance(value, dict) else value
    with open(os.path.join(home, ".bbs_browser.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


def capture(argv, keys, settle=1.2, state=None):
    """Starts the browser in a pseudo-terminal, feeds in `keys`, and returns
    the emulated final screen.

    `keys` is a list of strings (typed) and numbers (pause in seconds).
    """
    home = tempfile.mkdtemp(prefix="bbs-shot-")
    _seed_home(home, state=state)

    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)

    env = {
        **os.environ,
        "HOME": home,
        "TERM": "xterm-256color",
        "COLUMNS": str(COLS),
        "LINES": str(ROWS),
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": ROOT,
        # Without this, `keyring`'s startup probe (see vault.py) hits the real
        # OS keychain and macOS pops up a blocking "Allow access" dialog —
        # freezing the capture. The null backend skips straight to the DB
        # fallback, exactly like a headless Linux box with no keyring daemon.
        "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
    }
    env.pop("ANTHROPIC_API_KEY", None)

    pid, fd = pty.fork()
    if pid == 0:  # child process
        os.chdir(ROOT)
        os.execve(sys.executable, [sys.executable, "-m", "bbs_browser", *argv], env)

    try:
        import fcntl
        import struct
        import termios
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

        def pump(seconds):
            end = time.time() + seconds
            while time.time() < end:
                r, _, _ = select.select([fd], [], [], 0.05)
                if not r:
                    continue
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    return False
                if not data:
                    return False
                stream.feed(data)
            return True

        pump(0.6)
        for item in keys:
            if isinstance(item, (int, float)):
                pump(item)
            else:
                os.write(fd, item.encode())
                pump(0.35)
        pump(settle)
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass
        os.close(fd)
        shutil.rmtree(home, ignore_errors=True)

    return screen


# --- Scenes ------------------------------------------------------------
ESC = "\x1b"

# argv = CLI arguments, keys = key sequence (number = pause in seconds),
# settle = trailing wait, state = deviations from the default profile.
SCENES = {
    "01-handshake": dict(
        argv=[], keys=[4.6], settle=0.2,
        state={"ui": {"fast": False}},   # without fast, the handshake plays out visibly
    ),
    "02-main-board": dict(
        argv=["--no-handshake"], keys=[2.0], settle=1.0,
    ),
    "03-page": dict(
        # without images: this one should show off the two-column newspaper layout
        argv=["--no-handshake", "--no-images",
              "https://en.wikipedia.org/wiki/Bulletin_board_system"],
        keys=[5.0], settle=2.0,
    ),
    "04-tables": dict(
        # infobox of the Wikipedia page: demonstrates the ASCII table typesetting
        argv=["--no-handshake", "--no-images",
              "https://en.wikipedia.org/wiki/Commodore_64"],
        keys=[6.0], settle=2.0,
    ),
    "05-links": dict(
        argv=["--no-handshake", "https://lobste.rs"],
        # dismiss the MORE prompt first, otherwise the link panel hangs below the page
        keys=[5.0, "q\n", 0.8, "l\n"], settle=1.5,
    ),
    # ESC first: the main menu runs as a lightbar, otherwise the bar swallows
    # the input and selects the highlighted favorite instead.
    "06-config": dict(
        argv=["--no-handshake"], keys=[2.0, ESC, 0.5, "c\n", 0.8, "3\n"], settle=1.2,
    ),
    "07-games": dict(
        argv=["--no-handshake"],
        # drop a few pieces so the field doesn't look empty
        keys=[2.0, ESC, 0.5, "game stacker\n", 1.5,
              "a", "a", " ", 0.4, "d", "w", " ", 0.4, "d", "d", "d", " ", 0.4,
              "a", "w", " ", 0.4, "d", "d", 0.6], settle=1.0,
    ),
    "08-arcade": dict(
        argv=["--no-handshake"], keys=[2.0, ESC, 0.5, "game\n"], settle=1.2,
    ),
    "09-help": dict(
        argv=["--no-handshake"], keys=[2.0, ESC, 0.5, "?\n"], settle=1.2,
    ),
    "10-gopher": dict(
        argv=["--no-handshake", "gopher://gopher.floodgap.com"],
        keys=[5.0], settle=2.0,
    ),
    "11-german": dict(
        argv=["--no-handshake", "--lang", "de"], keys=[2.0], settle=1.0,
        state={"ui": {"lang": "de"}},
    ),
    "12-weather": dict(
        argv=["--no-handshake"], keys=[2.0, ESC, 0.5, "we\n"], settle=2.5,
        state={"weather": {
            "place": "Zürich, Schweiz",
            "lat": 47.3769, "lon": 8.5417,
            "tz": "Europe/Zurich", "units": "metric",
        }},
    ),
}


def main():
    wanted = sys.argv[1:] or list(SCENES)
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in wanted:
        if name not in SCENES:
            print(f"unbekannte Szene: {name}", file=sys.stderr)
            continue
        scene = SCENES[name]
        print(f"-> {name} ...", flush=True)
        screen = capture(scene["argv"], scene["keys"],
                         settle=scene["settle"], state=scene.get("state"))
        path = os.path.join(OUT_DIR, f"{name}.png")
        size = render_png(screen, path)
        filled = sum(1 for y in range(ROWS) for x in range(COLS)
                     if (screen.buffer[y][x].data or " ").strip())
        print(f"   {path}  {size[0]}x{size[1]}  ({filled} Zeichen)")


if __name__ == "__main__":
    main()
