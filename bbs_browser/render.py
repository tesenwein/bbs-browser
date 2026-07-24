"""Automatic page layout: every block is set at full screen width — titles,
boxes, rules and body copy alike. A terminal is read in one column."""

import re
import textwrap

from . import bigtext
from .constants import BOLD, DIM, MARKER_RE, RESET, screen_width, screen_lines
from .images import halfblock_lines, rgb_halfblock_lines
from .i18n import t

RAW = "__raw__"                    # Line is already styled, print directly


def _wrap_text(content, width, blank=True):
    lines = [(None, w) for w in (textwrap.wrap(content, width) or [""])]
    return lines + [(None, "")] if blank else lines


FRAME_CHARS = set("┌┬┐├┼┤└┴┘─│═╪╞╡")

CODE_COMMENT_RE = re.compile(r"^\s*(#(?!!)|//|--(\s|$)|;|/\*|\*\s|<!--)")
CODE_STRING_RE = re.compile(r'"[^"]*"')


def _style_code(term_color, line):
    """Code line with a dimmed gutter: comments dimmed, strings bold —
    subtle enough that non-code in <pre> (ASCII art, logs) also stays
    readable."""
    if CODE_COMMENT_RE.match(line):
        return DIM + "│ " + line + RESET
    body = CODE_STRING_RE.sub(lambda m: BOLD + m.group(0) + RESET + term_color, line)
    return DIM + "│ " + RESET + term_color + body


def _style_frame(term_color, line):
    """Frame characters dimmed, text in full terminal color."""
    out, in_frame = [], False
    for ch in line:
        if (ch in FRAME_CHARS) != in_frame:
            in_frame = not in_frame
            out.append(DIM if in_frame else RESET + term_color)
        out.append(ch)
    return "".join(out)


def _banner_lines(content):
    """Poster-style title in block lettering with an underline — the eye-
    catcher of a designed BBS page. If the block lettering doesn't fit the
    width, it falls back to a plain bold line."""
    big = bigtext.render_block(content, screen_width())
    if big:
        out = [(BOLD, bl) for bl in big]
        rule = min(max(len(bl) for bl in big), screen_width())
        return out + [(DIM, "─" * rule)]
    upper = content.upper()
    out = [(BOLD, w) for w in (textwrap.wrap(upper, screen_width()) or [""])]
    return out + [(DIM, "─" * min(len(upper), screen_width()))]


def _frame_lines(term_color, content):
    """Text in a double ANSI box — for lead paragraphs and key statements.
    Frame dimmed, content in terminal color."""
    width = screen_width()
    inner = width - 4
    body = textwrap.wrap(content, inner) or [""]
    edge = DIM + "╔" + "═" * (width - 2) + "╗" + RESET
    foot = DIM + "╚" + "═" * (width - 2) + "╝" + RESET
    out = [(RAW, edge)]
    for w in body:
        out.append((RAW, DIM + "║ " + RESET + term_color + w.ljust(inner) + DIM + " ║" + RESET))
    out.append((RAW, foot))
    return out


def _topicbar_lines(content):
    """Section bar with the title set into the rule:
    ──═[ RUBRIK ]═──────────────────────────────  The workhorse between the
    poster title and the body copy — a board announced every section this
    way."""
    width = screen_width()
    label = content.upper()[:max(4, width - 12)]
    head = DIM + "──═[ " + RESET + BOLD + label + RESET + DIM + " ]═"
    fill = width - (len(label) + 8)   # "──═[ " + label + " ]═"
    return [(RAW, head + "─" * max(fill, 0) + RESET)]


SHADOW = "▒"


def _plaque_lines(term_color, content):
    """Single-line box with a drop shadow — the little sign a board nailed
    up for a key statement. Louder than the frame, and unmistakably 1985."""
    width = screen_width() - 1     # the shadow takes the last column
    inner = width - 4
    body = textwrap.wrap(content, inner) or [""]
    out = [(RAW, DIM + "┌" + "─" * (width - 2) + "┐" + RESET)]
    for w in body:
        out.append((RAW, DIM + "│ " + RESET + term_color + w.ljust(inner)
                    + DIM + " │" + SHADOW + RESET))
    out.append((RAW, DIM + "└" + "─" * (width - 2) + "┘" + SHADOW + RESET))
    out.append((RAW, DIM + " " + SHADOW * width + RESET))
    return out


def _notice_lines(term_color, content):
    """Callout on a solid bar: a heavy left rule and a bang. For warnings,
    editor's notes, everything the board wanted read twice. Cheaper on the
    eye than a full box, so it can appear more than once on a page."""
    width = screen_width()
    body = textwrap.wrap(content, width - 4) or [""]
    out = []
    for i, w in enumerate(body):
        mark = BOLD + "! " + RESET + term_color if i == 0 else "  "
        out.append((RAW, DIM + "▌ " + RESET + term_color + mark + w))
    return out


def _ticker_lines(content):
    """One dimmed line between arrows: >>> DATELINE, KICKER, BYLINE <<<
    Everything that labels a page without being a heading."""
    width = screen_width()
    label = " ".join(content.upper().split())[:width - 10]
    return [(RAW, DIM + ">>> " + label + " <<<" + RESET)]


def _tag_group(rows, gid):
    """Marks lines as belonging to one group — the pager then won't break
    in the middle of it (block-lettering title, images)."""
    return [(r[0], r[1], gid) for r in rows]


def _one_liner(block, width):
    """Does the paragraph fit on a single line?"""
    return len(textwrap.wrap(block.get("content", ""), width) or [""]) <= 1


def layout_page(page, term_color):
    """Lays out the page — one column, full screen width, from the poster
    title down to the last line of body copy."""
    lines = []
    run = []  # Accumulated body-text blocks of the current section

    def blank_after(i, width):
        """When is there a blank line between two body-text blocks.

        Between two list items it's left out — otherwise every list would
        sprawl across half the screen. Same between two one-liners: news
        pages string paragraph after paragraph, each carrying just one
        sentence. With a blank line between them, half the page would be
        air and the eye finds no anchor. A paragraph that itself runs over
        several lines still gets its blank line — there it actually
        separates something."""
        nxt = run[i + 1] if i + 1 < len(run) else None
        if nxt is None:
            return True
        if run[i].get("tight") and nxt.get("tight"):
            return False
        return not (_one_liner(run[i], width) and _one_liner(nxt, width))

    def flush_run():
        if not run:
            return
        for i, b in enumerate(run):
            lines.extend(_wrap_text(b["content"], screen_width(), blank_after(i, screen_width())))
        run.clear()

    for b in page.blocks:
        if b["type"] == "text":
            run.append(b)
            continue
        flush_run()
        if b["type"] == "heading":
            content = b["content"].upper()
            # Bold poster titles like the intro logo — but only if the
            # title fits the width as block lettering; otherwise the plain
            # line.
            big = bigtext.render_block(b["content"], screen_width()) if b.get("big") else None
            head = []
            if big:
                head.extend((BOLD, bl) for bl in big)
                rule = max(len(bl) for bl in big)
                head.append((DIM, "─" * min(rule, screen_width())))
            else:
                head.extend((BOLD, w) for w in textwrap.wrap(content, screen_width()) or [""])
                head.append((DIM, "─" * min(len(content), screen_width())))
            lines.extend(_tag_group(head, f"head{len(lines)}"))
            lines.append((None, ""))
        elif b["type"] == "banner":
            lines.extend(_tag_group(_banner_lines(b["content"]), f"ban{len(lines)}"))
            lines.append((None, ""))
        elif b["type"] == "frame":
            lines.extend(_frame_lines(term_color, b["content"]))
            lines.append((None, ""))
        elif b["type"] == "topicbar":
            lines.extend(_tag_group(_topicbar_lines(b["content"]),
                                    f"topic{len(lines)}"))
            lines.append((None, ""))
        elif b["type"] == "plaque":
            lines.extend(_tag_group(_plaque_lines(term_color, b["content"]),
                                    f"plaq{len(lines)}"))
            lines.append((None, ""))
        elif b["type"] == "notice":
            lines.extend(_tag_group(_notice_lines(term_color, b["content"]),
                                    f"note{len(lines)}"))
            lines.append((None, ""))
        elif b["type"] == "ticker":
            lines.extend(_ticker_lines(b["content"]))
            lines.append((None, ""))
        elif b["type"] == "rule":
            lines.append((DIM, "─" * screen_width()))
            lines.append((None, ""))
        elif b["type"] == "pre":
            if any(c.isalnum() for c in b["content"]):
                for raw in b["content"].splitlines():
                    lines.append((RAW, _style_code(term_color, raw[:screen_width() - 2])))
            else:  # Pure line drawings (hr) stay simply dimmed
                for raw in b["content"].splitlines():
                    lines.append((DIM, raw[:screen_width()]))
            lines.append((None, ""))
        elif b["type"] == "md":
            # AI markdown, set with rich in the phosphor tone. Already
            # styled, hence RAW — the color is only known here (color_auto).
            from .markdown import render as render_md

            for styled in render_md(b["content"], term_color):
                lines.append((RAW, styled))
            lines.append((None, ""))
        elif b["type"] == "table":
            # Frame dimmed, content in terminal color — otherwise the
            # table drowns in its own frame.
            for raw in b["lines"]:
                lines.append((RAW, _style_frame(term_color, raw[:screen_width()])))
            lines.append((None, ""))
        elif b["type"] == "image":
            # Mark label and image lines as one group, so the MORE prompt
            # doesn't cut through the middle of an image.
            gid = f"img{len(lines)}"
            lines.append((BOLD, t("render.image_label", alt=b['alt']), gid))
            if b.get("rgb"):
                # Multi-color mode: real image colors, no phosphor tint.
                for raw in rgb_halfblock_lines(b["rgb"]):
                    lines.append((RAW, raw, gid))
            elif b.get("luma"):
                # Halfblock image: the phosphor tone the page is running in
                # is only known here. Already styled, so no more cutting —
                # a cut in the middle of an escape sequence would break the
                # line.
                for raw in halfblock_lines(b["luma"], term_color):
                    lines.append((RAW, raw, gid))
            else:
                for art_line in b["lines"]:
                    lines.append((DIM, art_line[:screen_width()], gid))
            lines.append((None, ""))
    flush_run()
    return lines


def _mark_links(text, restore):
    """Bold [n] markers — links catch the eye when skimming."""
    return MARKER_RE.sub(lambda m: BOLD + m.group(0) + RESET + restore, text)


def _print_line(term, style, text):
    if getattr(term, "baud", 0):
        # Baud mode: push everything throttled through the "modem".
        base = term.color + ("" if style == RAW else (style or ""))
        term.emit(base + _mark_links(text, base) + RESET)
    elif style == RAW:
        print(term.color + _mark_links(text, term.color) + RESET)
    elif style:
        base = term.color + style
        print(base + _mark_links(text, base) + RESET)
    elif MARKER_RE.search(text):
        # The typing effect breaks escape sequences apart character by
        # character — so print markers bold in one piece and type the rest.
        pos = 0
        for m in MARKER_RE.finditer(text):
            term.type_out(text[pos:m.start()], delay=0.0015, newline=False)
            print(term.color + BOLD + m.group(0) + RESET, end="")
            pos = m.end()
        term.type_out(text[pos:], delay=0.0015)
    else:
        term.type_out(text, delay=0.0015)


def _split_pages(lines, per_page):
    """Splits lines into pages and keeps marked groups (images, titles)
    together: a page break NEVER falls in the middle of a group.

    If a group no longer fits on the page in progress, the break is moved
    before it. If a group is by itself taller than one page (a very tall
    image on a small terminal), it gets its own page and overflows there —
    the top edge scrolls away, but the MORE prompt no longer cuts through
    the middle of the image. Images are additionally capped to page height
    already at render time (images.render_image), so this overflow remains
    the exception."""
    pages, page, i = [], [], 0
    while i < len(lines):
        gid = lines[i][2] if len(lines[i]) > 2 else None
        if gid is None:
            group = [lines[i]]
        else:
            j = i
            while j < len(lines) and len(lines[j]) > 2 and lines[j][2] == gid:
                j += 1
            group = lines[i:j]
        # Break BEFORE, never through: as soon as the group would exceed
        # the page in progress, that page is closed and the group starts
        # fresh.
        if page and len(page) + len(group) > per_page:
            pages.append(page)
            page = []
        page.extend(group)
        # Close a full (or, from an overlong group, overfull) page, so the
        # next line starts on a fresh page.
        if len(page) >= per_page:
            pages.append(page)
            page = []
        i += len(group)
    if page:
        pages.append(page)
    return pages


def paginate(term, lines):
    """Displays lines page by page. Returns commands typed at the MORE prompt."""
    per_page = screen_lines()
    pages = _split_pages(lines, per_page)
    shown = 0
    for n, page in enumerate(pages):
        shown += len(page)
        try:
            for style, l in ((ln[0], ln[1]) for ln in page):
                _print_line(term, style, l)
        except KeyboardInterrupt:
            # Ctrl+C caught between two lines: skip the rest of the screen,
            # go straight to the MORE prompt (which resets term.skip again).
            term.skip = True
            print(RESET)
        if n + 1 < len(pages):
            pct = int(100 * shown / len(lines))
            term.rule(t("render.more_prompt", percent=pct))
            resp = term.prompt("> ")
            if resp.lower() == "q":
                return None
            if resp:
                return resp  # Command/link number straight from the MORE prompt
    return None
