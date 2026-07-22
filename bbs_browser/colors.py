"""Smart color mode: picks a matching phosphor color per page.

Source 1: the page's <meta name="theme-color"> — the brand color is mapped
to the nearest phosphor tone (by hue, like a tinted CRT screen). Source 2
(fallback, e.g. when the color is missing or too dark/gray): a stable
hash of the domain, so each "board" always appears in the same scheme.
"""

import colorsys
import hashlib
import re

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
