"""Retro table rendering: HTML tables and CSS grids as ASCII boxes.

Tables are drawn with box-drawing characters like a terminal program from
1985 — header row separated by a double line, cells wrapped, column widths
distributed so the table fits the terminal width.
"""

import textwrap

# Frame in the classic single-line style; the header row is separated by
# a double line (CP437 look of the old DOS programs).
TL, TM, TR = "┌", "┬", "┐"
ML, MM, MR = "├", "┼", "┤"
BL, BM, BR = "└", "┴", "┘"
HL, VL = "─", "│"
HDL, HDM = "═", "╪"
HDLL, HDRR = "╞", "╡"

MIN_COL = 6          # no column gets squeezed narrower than this
MAX_TABLE_COLS = 8   # nobody reads wider tables in a terminal anyway


def _col_widths(rows, cols, width):
    """Distributes the available width across the columns: first by natural
    demand, then the widest columns are shrunk until it fits.
    Returns None if even MIN_COL per column no longer fits."""
    overhead = 3 * cols + 1          # "| " + " " per column + closing "|"
    avail = width - overhead
    if avail < MIN_COL * cols:
        return None

    natural = [max((len(r[i]) for r in rows), default=0) or 1 for i in range(cols)]
    widths = natural[:]
    while sum(widths) > avail:
        # Always shrink the currently widest column by one — this keeps
        # narrow columns (year, number) intact and only trims text columns.
        widest = max(range(cols), key=lambda i: widths[i])
        if widths[widest] <= MIN_COL:
            return None
        widths[widest] -= 1
    return widths


def _row_lines(cells, widths):
    """One table row with wrapped cells — as tall as the tallest cell,
    shorter cells are padded with whitespace."""
    wrapped = [textwrap.wrap(c, widths[i]) or [""] for i, c in enumerate(cells)]
    height = max(len(w) for w in wrapped)
    out = []
    for line in range(height):
        parts = [(w[line] if line < len(w) else "").ljust(widths[i])
                 for i, w in enumerate(wrapped)]
        out.append(VL + " " + (" " + VL + " ").join(parts) + " " + VL)
    return out


def render_table(rows, has_header, width):
    """Renders rows (a list of cell lists) as an ASCII table.
    Returns None if the table doesn't reasonably fit the width —
    the caller then lets it flow as normal text instead."""
    if not rows:
        return None
    cols = max(len(r) for r in rows)
    if cols < 2 or cols > MAX_TABLE_COLS:
        return None
    grid = [list(r) + [""] * (cols - len(r)) for r in rows]

    widths = _col_widths(grid, cols, width)
    if widths is None:
        return None

    def rule(left, mid, right, fill=HL):
        return left + mid.join(fill * (w + 2) for w in widths) + right

    lines = [rule(TL, TM, TR)]
    body_start = 0
    if has_header:
        lines += _row_lines(grid[0], widths)
        lines.append(rule(HDLL, HDM, HDRR, HDL))
        body_start = 1
    for i, row in enumerate(grid[body_start:]):
        if i:
            lines.append(rule(ML, MM, MR))
        lines += _row_lines(row, widths)
    lines.append(rule(BL, BM, BR))
    return lines


INFOBOX_LABEL = 18   # width of the label column in the info box


def render_infobox(rows, width):
    """Renders a fact sheet (Wikipedia infobox & co.) as a box:
    label on the left, value on the right. rows is a list of
    (label, value); label=None marks a subheading."""
    if not rows:
        return None
    label_w = min(INFOBOX_LABEL, max((len(l) for l, _ in rows if l), default=0)) or 1
    value_w = width - label_w - 7
    if value_w < MIN_COL:
        return None

    inner = label_w + value_w + 3   # full width including the separator column
    split = [label is not None for label, _ in rows]

    def rule(left, mid, right, above, below):
        # Only place the middle junction where above AND below are actually
        # separated — otherwise a line would dangle into empty space.
        junction = mid if (above and below) else (TM if below else (BM if above else HL))
        return left + HL * (label_w + 2) + junction + HL * (value_w + 2) + right

    lines = [rule(TL, TM, TR, False, split[0])]
    for i, (label, value) in enumerate(rows):
        if i:
            lines.append(rule(ML, MM, MR, split[i - 1], split[i]))
        if label is None:
            for line in textwrap.wrap(value.upper(), inner) or [""]:
                lines.append(VL + " " + line.center(inner) + " " + VL)
            continue
        left = textwrap.wrap(label, label_w) or [""]
        right = textwrap.wrap(value, value_w) or [""]
        for row in range(max(len(left), len(right))):
            l = (left[row] if row < len(left) else "").ljust(label_w)
            r = (right[row] if row < len(right) else "").ljust(value_w)
            lines.append(VL + " " + l + " " + VL + " " + r + " " + VL)
    lines.append(rule(BL, BM, BR, split[-1], False))
    return lines


def render_cards(items, width):
    """Renders a card list (CSS grid, teaser tiles) as a single box with
    separated compartments — the terminal equivalent of a grid layout."""
    if len(items) < 2:
        return None
    inner = width - 4
    if inner < MIN_COL * 2:
        return None
    lines = [TL + HL * (width - 2) + TR]
    for i, item in enumerate(items):
        if i:
            lines.append(ML + HL * (width - 2) + MR)
        for line in textwrap.wrap(item, inner) or [""]:
            lines.append(VL + " " + line.ljust(inner) + " " + VL)
    lines.append(BL + HL * (width - 2) + BR)
    return lines
