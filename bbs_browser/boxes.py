"""Box-drawing building blocks — the CP437 frame math shared across the UI.

Pure string builders: callers add their own colors/attributes around the
returned lines. Widths are total line widths including both border chars.
"""


def seg(title, width):
    """Box heading in the classic style: ─[ TITLE ]──────"""
    head = f"─[ {title} ]" if title else ""
    return head[:width].ljust(width, "─")


def double_top(width):
    return "╔" + "═" * (width - 2) + "╗"


def double_bottom(width):
    return "╚" + "═" * (width - 2) + "╝"


def double_divider(width, left="╟", right="╢"):
    return left + "─" * (width - 2) + right


def single_top(width, title=""):
    return "┌" + seg(title, width - 2) + "┐"


def single_bottom(width):
    return "└" + "─" * (width - 2) + "┘"


def split_top(col_l, col_r, title_l="", title_r=""):
    """Top edge of a two-column box: ┌─[ L ]──┬─[ R ]──┐"""
    return "┌" + seg(title_l, col_l) + "┬" + seg(title_r, col_r) + "┐"


def split_bottom(col_l, col_r):
    return "└" + "─" * col_l + "┴" + "─" * col_r + "┘"
