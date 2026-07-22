"""AI output is Markdown — this is where it's typeset for the phosphor terminal.

All AI texts (SysOp chat, agent, bulletins, RetroNet caller) come back as
Markdown. `rich` (the rich CLI toolkit) renders it to terminal text; a
monochrome filter discards rich's own colors and keeps only the attributes
(bold/dim/italic/underline), so the retro look stays in a single phosphor
tone. If `rich` is missing, everything falls back to plain text.
"""

import io
import re

from .constants import RESET, screen_width

# SGR sequences (\033[...m). We keep only attribute codes, no colors:
# 0 reset, 1 bold, 2 dim, 3 italic, 4 underline and their cancellations.
_SGR_RE = re.compile(r"\033\[([0-9;]*)m")
_KEEP = {"", "0", "1", "2", "3", "4", "22", "23", "24"}

_CONSOLE_THEME = None

# Emoji and pictograms have no place on a BBS terminal:
# they break the column width and the CP437 look.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF\U0000FE0E\U0000FE0F\U0000200D\U0001F1E6-\U0001F1FF]"
)

# Pictogram variants of normal punctuation: map them to their ASCII
# counterpart before the emoji filter runs, instead of deleting them outright
# (otherwise e.g. "73!" would become "73").
_PUNCT_EMOJI_MAP = {
    "❗": "!",  # ❗ heavy exclamation mark
    "❕": "!",  # ❕ white exclamation mark
    "‼": "!!",  # ‼ double exclamation mark
    "❓": "?",  # ❓ black question mark
    "❔": "?",  # ❔ white question mark
    "⁉": "!?",  # ⁉ exclamation question mark
}
_PUNCT_EMOJI_RE = re.compile("[" + "".join(_PUNCT_EMOJI_MAP) + "]")


# Markdown images: ![alt](url "title"). The AI drops these into chat replies
# just like a web page carries <img> — so they get the same treatment.
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")


def split_images(text):
    """Splits markdown into ("text", chunk) and ("image", alt, url) segments.

    An image on its own line becomes its own segment; everything around it
    stays markdown for rich. Returns a single text segment if there is no
    image at all.
    """
    segments = []
    pos = 0
    for m in _IMAGE_RE.finditer(text or ""):
        before = text[pos:m.start()]
        if before.strip():
            segments.append(("text", before))
        segments.append(("image", m.group(1).strip(), m.group(2)))
        pos = m.end()
    rest = (text or "")[pos:]
    if rest.strip() or not segments:
        segments.append(("text", rest))
    return segments


def strip_emoji(text):
    """Removes emoji/pictograms and cleans up the double spaces that
    results from doing so."""
    text = _PUNCT_EMOJI_RE.sub(lambda m: _PUNCT_EMOJI_MAP[m.group(0)], text)
    cleaned = _EMOJI_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return re.sub(r"[ \t]+$", "", cleaned, flags=re.M)


def _theme():
    """rich theme that maps the Markdown elements to plain attributes —
    no colorful headings, so the phosphor tone stays undisturbed."""
    global _CONSOLE_THEME
    if _CONSOLE_THEME is None:
        from rich.theme import Theme

        _CONSOLE_THEME = Theme(
            {
                "markdown.h1": "bold",
                "markdown.h2": "bold",
                "markdown.h3": "bold",
                "markdown.h4": "bold",
                "markdown.h5": "bold",
                "markdown.h6": "bold",
                "markdown.item.bullet": "bold",
                "markdown.item.number": "bold",
                "markdown.code": "dim",
                "markdown.code_block": "dim",
                "markdown.block_quote": "dim italic",
                "markdown.link": "underline",
                "markdown.link_url": "dim",
                "markdown.hr": "dim",
                "markdown.strong": "bold",
                "markdown.emph": "italic",
            },
            inherit=True,
        )
    return _CONSOLE_THEME


def available():
    """True if rich is installed (bundled in the 'ai' extra)."""
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _monochrome(match):
    """Keeps only the attribute parameters of an SGR sequence, discards all colors."""
    kept = [p for p in match.group(1).split(";") if p in _KEEP]
    return "\033[" + ";".join(kept) + "m" if kept else ""


def render(text, color, width=None):
    """Markdown -> finished, styled terminal lines (list without line wrap).

    Each line starts with the phosphor `color`; internal rich resets are
    expanded to `RESET + color` so the tone holds across the whole line. The
    caller appends a `RESET` at the end. Without rich, the plain text comes
    back unchanged.
    """
    text = strip_emoji((text or "").strip())
    if not text:
        return []
    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        return [color + line for line in text.splitlines()]

    width = width or screen_width()
    buf = io.StringIO()
    console = Console(
        file=buf,
        width=width,
        force_terminal=True,
        color_system="standard",
        theme=_theme(),
        highlight=False,
    )
    console.print(Markdown(text, code_theme="ansi_dark"))
    mono = _SGR_RE.sub(_monochrome, buf.getvalue())
    tinted = mono.replace(RESET, RESET + color)
    # rich pads every line to the full width with spaces — strip that so
    # highlighting/text selection stays clean.
    return [color + line.rstrip() for line in tinted.rstrip("\n").splitlines()]
