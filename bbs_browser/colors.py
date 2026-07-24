"""Smart color mode: picks a matching phosphor color per page.

Source 1: the page's <meta name="theme-color"> — the brand color is mapped
to the nearest phosphor tone (by hue, like a tinted CRT screen). Source 2
(fallback, e.g. when the color is missing or too dark/gray): a stable
hash of the domain, so each "board" always appears in the same scheme.
"""

import colorsys
import hashlib
import re
import sys

from .constants import BOLD, DIM

# Retro CRT palette: (name, ANSI escape, hue in degrees, RGB at full brightness)
# The RGB is the spelled-out tone of the 256-color index — needed where
# we have to darken the phosphor (images in half-block shading).
PHOSPHORS = [
    ("AMBER", "\033[38;5;214m", 33.0, (255, 175, 0)),
    ("GRUEN", "\033[38;5;46m", 120.0, (0, 255, 0)),
    ("CYAN", "\033[38;5;51m", 180.0, (0, 255, 255)),
    ("BLAU", "\033[38;5;75m", 210.0, (95, 175, 255)),
    ("MAGENTA", "\033[38;5;207m", 300.0, (255, 95, 255)),
    ("ROT", "\033[38;5;203m", 5.0, (255, 95, 95)),
]

DEFAULT_RGB = (255, 175, 0)   # amber — the default terminal's tone

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _parse_hex(value):
    m = HEX_RE.match((value or "").strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _nearest_phosphor(rgb):
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    # Brand colors that are too dark or gray don't carry a usable hue.
    if s < 0.25 or v < 0.35:
        return None
    hue = h * 360.0
    return min(PHOSPHORS, key=lambda p: min(abs(p[2] - hue), 360.0 - abs(p[2] - hue)))


def _domain_phosphor(domain):
    domain = (domain or "").lower().removeprefix("www.")
    digest = hashlib.sha1(domain.encode()).digest()
    return PHOSPHORS[digest[0] % len(PHOSPHORS)]


def phosphor_rgb(ansi):
    """RGB for the currently configured terminal escape. Unknown escapes
    (e.g. from the config file) fall back to amber."""
    for _, escape, _, rgb in PHOSPHORS:
        if escape == ansi:
            return rgb
    return DEFAULT_RGB


def pick_color(theme_color, domain):
    """Returns (name, ansi) for a page."""
    rgb = _parse_hex(theme_color)
    phosphor = _nearest_phosphor(rgb) if rgb else None
    if phosphor is None:
        phosphor = _domain_phosphor(domain)
    return phosphor[0], phosphor[1]


# --- Multi-color mode: role palette in classic ANSI-BBS style -------------
#
# Every drawing routine in the app styles with a single terminal color plus
# the DIM/BOLD attributes: frames, rules and tickers are DIM, headings and
# link markers are BOLD, body copy is plain. In multi mode those attributes
# are translated into role colors at the last moment before the terminal —
# like swapping the palette registers on a CGA card. That colors the whole
# app consistently without touching a single drawing routine.

MULTI_TEXT = "\033[38;5;250m"                 # body copy — light gray
MULTI_ACCENT = "\033[38;5;220m"               # BOLD: headings, links — yellow
MULTI_FRAME = DIM + "\033[38;5;110m"          # DIM: frames, rules — steel blue


class _RoleStream:
    """stdout wrapper that rewrites the attribute escapes into the role
    palette. Everything else passes through untouched."""

    def __init__(self, raw):
        self._raw = raw
        self.active = False

    def write(self, s):
        if self.active and "\033[" in s:
            s = s.replace(BOLD, BOLD + MULTI_ACCENT).replace(DIM, MULTI_FRAME)
        return self._raw.write(s)

    def __getattr__(self, name):
        return getattr(self._raw, name)


def set_multi(on):
    """Switches the role palette on or off. The wrapper is installed lazily
    on first use and then stays in place, inert while inactive."""
    stream = sys.stdout
    if not isinstance(stream, _RoleStream):
        if not on:
            return
        stream = _RoleStream(stream)
        sys.stdout = stream
    stream.active = bool(on)


def multi_active():
    return isinstance(sys.stdout, _RoleStream) and sys.stdout.active
