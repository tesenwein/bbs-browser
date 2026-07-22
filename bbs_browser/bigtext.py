"""Large block titles in BBS style — like the intro logo, but for any
text. A block font renders as a bold heading.

AI-designed pages render their headings as proper poster titles rather than
single bold lines. If a title is too long for screen width, the renderer
falls back to the simple heading (render_block returns None).

pyfiglet is a core dependency: the renderer sets titles in exactly the
font of the intro logo ('ANSI Shadow') — same look, more characters and
automatic word wrapping, even without the ai extra. If the lib is missing
(very old installation), the bundled 5-line block font kicks in as
a fallback; so the renderer stays robust.

Umlauts are unknown to both Figlet font and fallback font, so they're
transliterated first (Ä->AE, ß->SS ...), else 'Über' becomes 'BER'."""

FIGLET_FONT = "ansi_shadow"        # font of the intro logo

FILL = "█"
EMPTY = " "
HEIGHT = 5          # each glyph of the fallback font is exactly 5 lines high
GAP = 1             # blank columns between two glyphs

_UMLAUTS = {
    "Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS",
    "ä": "AE", "ö": "OE", "ü": "UE",
    "À": "A", "Á": "A", "Â": "A", "É": "E", "È": "E", "Ê": "E",
    "Í": "I", "Ó": "O", "Ô": "O", "Ú": "U", "Ç": "C", "Ñ": "N",
    "–": "-", "—": "-", "’": "'", "‘": "'", "„": '"', "“": '"',
}


def _normalize(text):
    """Prepare title for block font: transliterate umlauts,
    uppercase, collapse multiple spaces."""
    out = []
    for ch in text:
        out.append(_UMLAUTS.get(ch, ch))
    return " ".join("".join(out).upper().split())


# -- Block font ---------------------------------------------------------
#
# Each glyph: 5 lines of equal width, '#' = bar, ' ' = empty.

_GLYPHS = {
    "A": [" ## ", "#  #", "####", "#  #", "#  #"],
    "B": ["### ", "#  #", "### ", "#  #", "### "],
    "C": [" ###", "#   ", "#   ", "#   ", " ###"],
    "D": ["### ", "#  #", "#  #", "#  #", "### "],
    "E": ["####", "#   ", "### ", "#   ", "####"],
    "F": ["####", "#   ", "### ", "#   ", "#   "],
    "G": [" ###", "#   ", "# ##", "#  #", " ###"],
    "H": ["#  #", "#  #", "####", "#  #", "#  #"],
    "I": ["###", " # ", " # ", " # ", "###"],
    "J": ["  ##", "   #", "   #", "#  #", " ## "],
    "K": ["#  #", "# # ", "##  ", "# # ", "#  #"],
    "L": ["#   ", "#   ", "#   ", "#   ", "####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "O": [" ## ", "#  #", "#  #", "#  #", " ## "],
    "P": ["### ", "#  #", "### ", "#   ", "#   "],
    "Q": [" ## ", "#  #", "#  #", "# # ", " ## #"],
    "R": ["### ", "#  #", "### ", "# # ", "#  #"],
    "S": [" ###", "#   ", " ## ", "   #", "### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#  #", "#  #", "#  #", "#  #", " ## "],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "Y": ["#   #", " # # ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "   # ", "  #  ", " #   ", "#####"],
    "0": [" ## ", "#  #", "#  #", "#  #", " ## "],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["### ", "   #", " ## ", "#   ", "####"],
    "3": ["### ", "   #", " ## ", "   #", "### "],
    "4": ["#  #", "#  #", "####", "   #", "   #"],
    "5": ["####", "#   ", "### ", "   #", "### "],
    "6": [" ## ", "#   ", "### ", "#  #", " ## "],
    "7": ["####", "   #", "  # ", " #  ", " #  "],
    "8": [" ## ", "#  #", " ## ", "#  #", " ## "],
    "9": [" ## ", "#  #", " ###", "   #", " ## "],
    " ": ["  ", "  ", "  ", "  ", "  "],
    ".": [" ", " ", " ", " ", "#"],
    ",": ["  ", "  ", "  ", " #", "# "],
    "!": ["#", "#", "#", " ", "#"],
    "?": ["### ", "   #", " ## ", "    ", " #  "],
    "-": ["   ", "   ", "###", "   ", "   "],
    "+": ["   ", " # ", "###", " # ", "   "],
    ":": [" ", "#", " ", "#", " "],
    "'": ["#", "#", " ", " ", " "],
    "/": ["   #", "  # ", " #  ", "#   ", "    "],
    "&": [" ## ", "#  #", " ## ", "# # ", " ###"],
    "*": ["     ", "# # #", " ### ", "# # #", "     "],
    "#": [" # # ", "#####", " # # ", "#####", " # # "],
    "(": [" #", "# ", "# ", "# ", " #"],
    ")": ["# ", " #", " #", " #", "# "],
}


# Pad each glyph to equal line width — so concatenation
# stays column-true during rendering, even if a pattern was typed carelessly.
for _ch, _g in _GLYPHS.items():
    _w = max(len(r) for r in _g)
    _GLYPHS[_ch] = [r.ljust(_w) for r in _g]
del _ch, _g, _w


def _glyph(ch):
    """Glyph for a character (uppercase), or None if unknown."""
    return _GLYPHS.get(ch)


def measure(text):
    """Width the text would take as a block title in characters —
    or None if a character has no glyph."""
    up = text.upper()
    width = 0
    first = True
    for ch in up:
        g = _glyph(ch)
        if g is None:
            return None
        if not first:
            width += GAP
        width += len(g[0])
        first = False
    return width


def render_line(text):
    """Render a single text line as 5 block lines. Expects every
    character to have a glyph (else None). No word wrap — the caller
    handles that via render_block."""
    rows = [""] * HEIGHT
    first = True
    for ch in text.upper():
        g = _glyph(ch)
        if g is None:
            return None
        for r in range(HEIGHT):
            if not first:
                rows[r] += EMPTY * GAP
            rows[r] += g[r]
        first = False
    return [row.replace("#", FILL) for row in rows]


def _wrap_words(text, width):
    """Break the title word by word so each line as a block title fits
    in 'width' characters. None if a single word is too wide
    or a character has no glyph."""
    words = text.split()
    if not words:
        return None
    lines = []
    cur = ""
    for word in words:
        cand = word if not cur else cur + " " + word
        w = measure(cand)
        if w is None:
            return None
        if w <= width:
            cur = cand
            continue
        # No longer fits — close current line, start fresh.
        if cur:
            lines.append(cur)
        if measure(word) is None or measure(word) > width:
            return None
        cur = word
    if cur:
        lines.append(cur)
    return lines


def _render_builtin(text, width):
    """Block title with the bundled 5-line font (fallback)."""
    wrapped = _wrap_words(text, width)
    if not wrapped:
        return None
    out = []
    for i, line in enumerate(wrapped):
        block = render_line(line)
        if block is None:
            return None
        out.extend(block)
        if i != len(wrapped) - 1:
            out.append("")     # blank line between two title lines
    return out


# -- pyfiglet (optional) ------------------------------------------------

_figlet = None          # cached Figlet instance
_figlet_tried = False   # try import only once


def _figlet_instance():
    """Cache the Figlet instance with the intro font. None if pyfiglet
    is missing or the font can't be loaded."""
    global _figlet, _figlet_tried
    if _figlet_tried:
        return _figlet
    _figlet_tried = True
    try:
        from pyfiglet import Figlet
        _figlet = Figlet(font=FIGLET_FONT)
    except Exception:
        _figlet = None
    return _figlet


_HUGE = 100000     # never let pyfiglet wrap itself (else infinite loop)


def _figlet_lines(fig, text):
    """Render 'text' as Figlet blocks, WITHOUT letting pyfiglet wrap —
    too narrow a wrap makes pyfiglet hang. Return lines
    without empty border lines, or None."""
    try:
        fig.width = _HUGE
        art = fig.renderText(text)
    except Exception:
        return None
    lines = art.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines or None


def _figlet_width(fig, text):
    lines = _figlet_lines(fig, text)
    return max(len(l) for l in lines) if lines else None


def _render_figlet(text, width):
    """Block title in intro font via pyfiglet. Word wrap happens
    here — each line stays <= width. None if pyfiglet is missing or a
    single word is too wide by itself (then fallback / plain
    heading kicks in)."""
    fig = _figlet_instance()
    if fig is None:
        return None
    words = text.split()
    if not words:
        return None
    # Greedily pack words into lines whose block width stays <= width.
    rows = []           # finished line texts
    cur = ""
    for word in words:
        if _figlet_width(fig, word) is None or _figlet_width(fig, word) > width:
            return None     # this word doesn't fit by itself
        cand = word if not cur else cur + " " + word
        if _figlet_width(fig, cand) <= width:
            cur = cand
        else:
            rows.append(cur)
            cur = word
    if cur:
        rows.append(cur)
    out = []
    for i, row in enumerate(rows):
        block = _figlet_lines(fig, row)
        if block is None:
            return None
        out.extend(l.rstrip() for l in block)
        if i != len(rows) - 1:
            out.append("")     # blank line between two title lines
    return out or None


def render_block(text, width):
    """Complete block title: a list of finished text lines (no color), word-wrapped,
    each block line <= width. Prefers intro font (pyfiglet)
    and falls back to bundled block font otherwise. None if the
    title can't render as block font at all (too wide or unknown)."""
    if not text or not text.strip() or width < 8:
        return None
    norm = _normalize(text)
    if not norm:
        return None
    return _render_figlet(norm, width) or _render_builtin(norm, width)
