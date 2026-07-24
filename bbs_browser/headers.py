"""Page headers — 50 hand-drawn ANSI banners, one per domain.

On the first visit to a domain, a template is picked at random and recorded
in the state file under "headers"; from then on the page always gets the
same banner. Costs nothing, needs no AI key.

The templates are written out as Python expressions ("╔" + "═"*74 + "╗")
rather than counted-out raw strings: that way the column width is exact by
construction. Placeholders are format specs with precision, e.g.
"{name:^40.40}" — which centers *and* truncates, so long domains never
break the layout.
"""

import random

from .constants import BOLD, DIM, RESET
from .colors import multi_active
from .images import fetch_logo, halfblock_lines, rgb_halfblock_lines
from .state import load_section, save_section

W = 76                    # Total width of a banner in characters
MIN_TERM_WIDTH = W + 2    # Below this, the header is skipped


# -- Text building blocks ------------------------------------------------

SUBS = [
    "EST. 1985", "ONLINE 24H", "2400 BAUD ARQ", "NODE 3 OF 4",
    "MEMBERS ONLY", "NO CARRIER YET", "ANSI-BBS · CP437", "V.42BIS READY",
    "SYSOP ON DUTY", "PRESS ANY KEY", "ELITE ACCESS", "LONG DISTANCE OK",
    "1200/2400/9600", "FILE AREA OPEN", "MAIL WAITING", "HAYES COMPATIBLE",
]


def _fields(domain):
    """Text fields for a template's placeholders."""
    name = domain.upper()
    return {
        "name": name,
        "wide": " ".join(name),        # H E I S E . D E
        "low": domain.lower(),
        "sub": SUBS[sum(map(ord, domain)) % len(SUBS)],
    }


# -- The 50 templates -----------------------------------------------------
#
# Each template is a list of lines. Every line is exactly W characters
# wide once the placeholders have been filled in.

def _t01():
    return [
        "╔" + "═" * 74 + "╗",
        "║" + "{name:^74.74}" + "║",
        "╟" + "─" * 74 + "╢",
        "║" + "{sub:^74.74}" + "║",
        "╚" + "═" * 74 + "╝",
    ]


def _t02():
    return [
        "┌" + "─" * 74 + "┐",
        "│ " + "{wide:^72.72}" + " │",
        "└" + "─" * 74 + "┘",
    ]


def _t03():
    return [
        "▛" + "▀" * 74 + "▜",
        "▌" + "{name:^74.74}" + "▐",
        "▌" + "{sub:^74.74}" + "▐",
        "▙" + "▄" * 74 + "▟",
    ]


def _t04():
    return [
        "+" + "-" * 74 + "+",
        "|" + "{name:^74.74}" + "|",
        "+" + "-" * 74 + "+",
    ]


def _t05():
    return [
        "╭" + "─" * 74 + "╮",
        "│" + "{wide:^74.74}" + "│",
        "│" + "{sub:^74.74}" + "│",
        "╰" + "─" * 74 + "╯",
    ]


def _t06():
    # Box frame with drop shadow
    return [
        "┏" + "━" * 73 + "┓ ",
        "┃" + "{name:^73.73}" + "┃▒",
        "┗" + "━" * 73 + "┛▒",
        " " + "▒" * 73 + "  ",
    ]


def _t07():
    return [
        "░" * 76,
        "░░" + "{name:^72.72}" + "░░",
        "░" * 76,
    ]


def _t08():
    return [
        "█▀" + "▀" * 72 + "▀█",
        "█ " + "{wide:^72.72}" + " █",
        "█▄" + "▄" * 72 + "▄█",
    ]


def _t09():
    return [
        "═" * 76,
        "{name:^76.76}",
        "{sub:^76.76}",
        "═" * 76,
    ]


def _t10():
    return [
        "▄" * 76,
        "█" + "{name:^74.74}" + "█",
        "▀" * 76,
    ]


def _t11():
    # Gradient from outside to inside
    return [
        "░▒▓█" + "▀" * 68 + "█▓▒░",
        "░▒▓█" + "{name:^68.68}" + "█▓▒░",
        "░▒▓█" + "▄" * 68 + "█▓▒░",
    ]


def _t12():
    return [
        "█▓▒░" + " " * 68 + "░▒▓█",
        "█▓▒░" + "{wide:^68.68}" + "░▒▓█",
        "█▓▒░" + "{sub:^68.68}" + "░▒▓█",
        "█▓▒░" + " " * 68 + "░▒▓█",
    ]


def _t13():
    return [
        "▐" + "░▒▓" * 24 + "░▒▌",
        "▐" + "{name:^74.74}" + "▌",
        "▐" + "▓▒░" * 24 + "▓▒▌",
    ]


def _t14():
    return [
        "▁" * 76,
        "▏" + "{name:^74.74}" + "▕",
        "▔" * 76,
    ]


def _t15():
    return [
        "█" * 76,
        "██" + "{name:^72.72}" + "██",
        "██" + "{sub:^72.72}" + "██",
        "█" * 76,
    ]


def _t16():
    return [
        "▓" * 76,
        "▓▓▓" + "{name:<70.70}" + "▓▓▓",
        "▓" * 76,
    ]


def _t17():
    return [
        "▗" + "▄" * 74 + "▖",
        "▐" + "{wide:^74.74}" + "▌",
        "▝" + "▀" * 74 + "▘",
    ]


def _t18():
    return [
        "▒▒▒▒" + "▔" * 68 + "▒▒▒▒",
        "▒▒▒▒" + "{name:^68.68}" + "▒▒▒▒",
        "▒▒▒▒" + "▁" * 68 + "▒▒▒▒",
    ]


def _t19():
    return [
        "▄▀" * 38,
        " " + "{name:^74.74}" + " ",
        "▀▄" * 38,
    ]


def _t20():
    return [
        "█" + "▀▄" * 37 + "█",
        "█" + "{sub:^74.74}" + "█",
        "█" + "{name:^74.74}" + "█",
        "█" + "▄▀" * 37 + "█",
    ]


def _t21():
    return [
        "★" + "─" * 74 + "★",
        "│" + "{name:^74.74}" + "│",
        "★" + "─" * 74 + "★",
    ]


def _t22():
    return [
        "·" * 76,
        "·  ✦  " + "{name:^64.64}" + "  ✦  ·",
        "·" * 76,
    ]


def _t23():
    return [
        "◆" * 38 + "◇" * 38,
        "◆ " + "{wide:^72.72}" + " ◆",
        "◇" * 38 + "◆" * 38,
    ]


def _t24():
    return [
        "╔" + "═" * 74 + "╗",
        "║ ✶ " + "{name:^68.68}" + " ✶ ║",
        "║   " + "{sub:^68.68}" + "   ║",
        "╚" + "═" * 74 + "╝",
    ]


def _t25():
    return [
        "*" * 76,
        "*" + " " * 74 + "*",
        "*" + "{name:^74.74}" + "*",
        "*" + " " * 74 + "*",
        "*" * 76,
    ]


def _t26():
    return [
        "«" * 6 + "─" * 64 + "»" * 6,
        " " * 6 + "{name:^64.64}" + " " * 6,
        "«" * 6 + "─" * 64 + "»" * 6,
    ]


def _t27():
    return [
        "▪ ▫ " * 19,
        "▪" + "{name:^74.74}" + "▪",
        "▫ ▪ " * 19,
    ]


def _t28():
    return [
        "┅" * 76,
        "┇" + "{wide:^74.74}" + "┇",
        "┇" + "{sub:^74.74}" + "┇",
        "┅" * 76,
    ]


def _t29():
    return [
        "○" + "•" * 74 + "○",
        "•" + "{name:^74.74}" + "•",
        "○" + "•" * 74 + "○",
    ]


def _t30():
    return [
        "╲" * 76,
        "╲╲╲" + "{name:^70.70}" + "╲╲╲",
        "╱" * 76,
    ]


def _t31():
    # Circuit board: traces with solder pads
    return [
        "┌─┬─" + "┴" * 68 + "─┬─┐",
        "┤ ├ " + "{name:^68.68}" + " ┤ ├",
        "└─┴─" + "┬" * 68 + "─┴─┘",
    ]


def _t32():
    # Compact cassette
    return [
        "┌" + "─" * 74 + "┐",
        "│  ◎" + "─" * 30 + "{name:^12.12}" + "─" * 26 + "◎  │",
        "│  " + "▁" * 70 + "  │",
        "└" + "─" * 74 + "┘",
    ]


def _t33():
    # 5.25-inch floppy disk
    return [
        "┌" + "─" * 60 + "┬" + "─" * 13 + "┐",
        "│ " + "{name:<58.58}" + " │ " + "▓" * 11 + " │",
        "│ " + "{sub:<58.58}" + " │ " + "░" * 11 + " │",
        "└" + "─" * 60 + "┴" + "─" * 13 + "┘",
    ]


def _t34():
    # Modem with status LEDs
    return [
        "▛" + "▀" * 74 + "▜",
        "▌ ● ● ● ○  " + "{name:^53.53}" + "  CD RD SD ▐",
        "▙" + "▄" * 74 + "▟",
    ]


def _t35():
    # Barcode
    return [
        "▍▎▊▎" * 19,
        "{name:^76.76}",
        "▊▍▎▍" * 19,
    ]


def _t36():
    # Punched tape
    return [
        "○ " * 38,
        "│ " + "{wide:^72.72}" + " │",
        "○ " * 38,
    ]


def _t37():
    # Terminal window with title bar
    return [
        "┌─[ ■ ]" + "─" * 68 + "┐",
        "│ C:\\> " + "{low:<67.67}" + " │",
        "│ " + "{name:^72.72}" + " │",
        "└" + "─" * 74 + "┘",
    ]


def _t38():
    # Expansion card with contact strip
    return [
        "▄" * 76,
        "█ " + "{name:^72.72}" + " █",
        "█ " + "{sub:^72.72}" + " █",
        "█▄▄▄" + "██  " * 17 + "▄▄▄█",
    ]


def _t39():
    # Dot-matrix printer continuous paper
    return [
        "○│" + "─" * 72 + "│○",
        "○│" + "{name:^72.72}" + "│○",
        "○│" + "─" * 72 + "│○",
    ]


def _t40():
    # Control panel with toggle switches
    return [
        "╔" + "═" * 74 + "╗",
        "║ ▀▄▀▄ " + "{name:^62.62}" + " ▄▀▄▀ ║",
        "║ " + "{sub:^72.72}" + " ║",
        "╚" + "═" * 74 + "╝",
    ]


def _t41():
    # Marquee with light bulbs
    return [
        "●○" * 38,
        "○" + "{name:^74.74}" + "○",
        "●" + "{sub:^74.74}" + "●",
        "○●" * 38,
    ]


def _t42():
    # Sunrise, synthwave
    return [
        "▁▂▃▄▅▆▇█" + "{name:^60.60}" + "█▇▆▅▄▃▂▁",
        "▔" * 76,
        "▁▁▁▁" + "{sub:^68.68}" + "▁▁▁▁",
    ]


def _t43():
    # Pyramid
    return [
        " " * 30 + "▄" * 16 + " " * 30,
        " " * 20 + "▄" * 36 + " " * 20,
        "▄" * 76,
        "{name:^76.76}",
    ]


def _t44():
    # Wave
    return [
        "▂▄▆█▆▄▂" * 10 + "▂▄▆█▆▄",
        "{name:^76.76}",
        "█▆▄▂▄▆█" * 10 + "█▆▄▂▄▆",
    ]


def _t45():
    # Zebra stripes
    return [
        "▐█▌ " * 19,
        "{wide:^76.76}",
        "▐█▌ " * 19,
    ]


def _t46():
    # Perspective funnel
    return [
        "╲" + "─" * 74 + "╱",
        " ╲" + "{name:^72.72}" + "╱ ",
        "  ╲" + "{sub:^70.70}" + "╱  ",
        "   " + "─" * 70 + "   ",
    ]


def _t47():
    # Double frame with corner marks
    return [
        "╔══╗" + " " * 68 + "╔══╗",
        "╚══╝" + "{name:^68.68}" + "╚══╝",
        "╔══╗" + "{sub:^68.68}" + "╔══╗",
        "╚══╝" + " " * 68 + "╚══╝",
    ]


def _t48():
    # Ticker tape
    return [
        "◄◄ " + "─" * 70 + " ►►",
        "◄◄ " + "{name:^70.70}" + " ►►",
        "◄◄ " + "─" * 70 + " ►►",
    ]


def _t49():
    # Teletext block graphics
    return [
        "▘▝" * 38,
        "▖" + "{name:^74.74}" + "▗",
        "▌" + "{sub:^74.74}" + "▐",
        "▚▞" * 38,
    ]


def _t50():
    # Large closing frame with inner line
    return [
        "█" * 76,
        "█" + "▀" * 74 + "█",
        "█" + "{wide:^74.74}" + "█",
        "█" + "{sub:^74.74}" + "█",
        "█" + "▄" * 74 + "█",
        "█" * 76,
    ]


TEMPLATES = [
    _t01(), _t02(), _t03(), _t04(), _t05(), _t06(), _t07(), _t08(), _t09(), _t10(),
    _t11(), _t12(), _t13(), _t14(), _t15(), _t16(), _t17(), _t18(), _t19(), _t20(),
    _t21(), _t22(), _t23(), _t24(), _t25(), _t26(), _t27(), _t28(), _t29(), _t30(),
    _t31(), _t32(), _t33(), _t34(), _t35(), _t36(), _t37(), _t38(), _t39(), _t40(),
    _t41(), _t42(), _t43(), _t44(), _t45(), _t46(), _t47(), _t48(), _t49(), _t50(),
]


# -- Domain -> template mapping (persistent) -----------------------------

def template_for(domain):
    """Index of this domain's template. On first use, one is picked at
    random and saved; after that the page keeps its banner."""
    assigned = load_section("headers")
    if domain in assigned:
        idx = assigned[domain]
        if isinstance(idx, int) and 0 <= idx < len(TEMPLATES):
            return idx
    # Prefer templates not yet assigned, so the collection fills up before
    # the first one repeats.
    used = {i for i in assigned.values() if isinstance(i, int)}
    pool = [i for i in range(len(TEMPLATES)) if i not in used] or range(len(TEMPLATES))
    idx = random.choice(list(pool))
    assigned[domain] = idx
    save_section("headers", assigned)
    return idx


# -- Logo banner -----------------------------------------------------------
#
# Gives the page a usable logo, if it has one, over the randomly picked
# template: the real brand mark as ASCII art beats any random pattern.

ART_SLOT = "\x00art\x00"   # Placeholder for an art line within the frame


def art_height(art):
    """How many text lines a logo payload occupies. In block mode, two
    image rows share one text line."""
    if not art:
        return 0
    if isinstance(art, dict):
        rows = art.get("luma") or art.get("rgb") or []
        return len(rows) // 2 or len(art.get("lines") or [])
    return len(art)   # Legacy cache entries: plain character rows


def art_lines(art, term_color=""):
    """Logo payload -> finished, frame-width-centered lines.

    In block mode, the lines carry ANSI colors, so their visible width is
    NOT their character length — hence this is computed using the known
    raster width rather than .center()."""
    inner = W - 2
    if isinstance(art, dict) and (art.get("luma") or art.get("rgb")):
        rows = art.get("luma") or art["rgb"]
        raster = len(rows[0]) if rows else 0
        pad = max(0, (inner - raster) // 2)
        body = (rgb_halfblock_lines(rows) if art.get("rgb")
                else halfblock_lines(rows, term_color))
        return [
            " " * pad + line + " " * max(0, inner - raster - pad)
            for line in body
        ]
    lines = art.get("lines") if isinstance(art, dict) else art
    return [row.center(inner)[:inner] for row in lines or []]


def logo_template(rows):
    """Frame around a logo — same width and look as the 50 static templates,
    so the header doesn't break the grid. The `rows` art lines stay as
    placeholders; they're filled in only in render(), where the terminal's
    phosphor tone is known."""
    inner = W - 2
    lines = ["╔" + "═" * inner + "╗", "║" + " " * inner + "║"]
    lines += ["║" + ART_SLOT + "║"] * rows
    lines += ["║" + " " * inner + "║", "╟" + "─" * inner + "╢"]
    lines.append("║" + "{name:^%d.%d}" % (inner, inner) + "║")
    lines.append("║" + "{sub:^%d.%d}" % (inner, inner) + "║")
    lines.append("╚" + "═" * inner + "╝")
    return lines


def logo_art(domain, urls, mode="blocks"):
    """ASCII art of the page's logo, persistently cached.

    Candidates are tried in order until one yields something legible — a
    logo often fails because it's a pure silhouette with no interior
    drawing. The failure case is also remembered (empty list), otherwise
    every page visit would reload the same unusable files again. If the
    page changes its logos OR the render mode, the cache falls out on its
    own — entries without a mode date from the ASCII era and are refetched."""
    urls = [u for u in (urls or []) if u]
    color = mode == "blocks" and multi_active()
    cache = load_section("logos")
    entry = cache.get(domain)
    if (isinstance(entry, dict) and entry.get("urls") == urls
            and entry.get("mode") == mode and entry.get("color", False) == color):
        return entry.get("art") or None
    art = next((a for a in (fetch_logo(u, mode=mode, color=color) for u in urls) if a), None)
    cache[domain] = {"urls": urls, "mode": mode, "color": color, "art": art or []}
    save_section("logos", cache)
    return art


def _forget(section, domain):
    """Drop a domain's entry (or all of them) from a state section."""
    if domain is None:
        save_section(section, {})
        return
    entries = load_section(section)
    entries.pop(domain, None)
    save_section(section, entries)


def forget_logo(domain=None):
    """Discard the logo cache for a domain (or all domains)."""
    _forget("logos", domain)


# -- Output ------------------------------------------------------------

def render(domain, width, art=None, term_color=""):
    """Finished, filled-in banner lines — or [] if the terminal is too
    narrow or the domain is missing. Art lines are inserted rather than
    formatted: they carry no field names, but they do carry color codes."""
    if not domain or width < MIN_TERM_WIDTH:
        return []
    art_rows = art_lines(art, term_color) if art else []
    lines = logo_template(len(art_rows)) if art_rows else TEMPLATES[template_for(domain)]
    fields = _fields(domain)
    pad = " " * ((width - W) // 2)
    out, rows = [], iter(art_rows)
    for line in lines:
        if ART_SLOT in line:
            out.append(pad + line.replace(ART_SLOT, next(rows)))
        else:
            out.append(pad + line.format(**fields))
    return out


def show(term, domain, width, art=None):
    """Print the banner in the terminal color."""
    lines = render(domain, width, art, getattr(term, "color", ""))
    if not lines:
        return
    # For the logo banner, the brand mark carries the statement; otherwise
    # it's the middle line.
    art_rows = art_height(art)
    bold = range(2, 2 + art_rows) if art_rows else [len(lines) // 2]
    for i, line in enumerate(lines):
        # A colored art line already carries its own colors — a BOLD in
        # front of it would just wash it out and lighten it.
        if art_rows and i in bold and isinstance(art, dict) and art.get("luma"):
            term.emit(line)
            continue
        style = BOLD if i in bold else DIM
        term.emit(term.color + style + line + RESET)


def reset(domain=None):
    """Discard a domain's assignment (or all of them) — a new one is
    picked at random on the next visit."""
    _forget("headers", domain)
