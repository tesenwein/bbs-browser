"""The manual — a single source of truth for all features.

This list is the source for: the help ('?' and '? <command>'), the
command overview in navigation.py, and the internal SysOp tools
'funktionen_auflisten' / 'funktion_erklaeren'. New features are entered
ONLY here.
"""

from .i18n import t

NAVIGATION = t("manual.category_navigation")
SEITE = t("manual.category_content")
ABLAGE = t("manual.category_storage")
KI = t("manual.category_ai")
SYSTEM = t("manual.category_system")
SPIELE = t("manual.category_games")

# (command, syntax, category, short, long)
FEATURES = [
    ("nr", "<nr>", NAVIGATION, t("manual.nr_short"),
     t("manual.nr_long")),

    ("d", "d <url> | d <nr>", NAVIGATION, t("manual.d_short"),
     t("manual.d_long")),

    ("s", "s <text>", NAVIGATION, t("manual.s_short"),
     t("manual.s_long")),

    ("b", "b", NAVIGATION, t("manual.b_short"),
     t("manual.b_long")),

    ("f", "f", NAVIGATION, t("manual.f_short"),
     t("manual.f_long")),

    ("r", "r", NAVIGATION, t("manual.r_short"),
     t("manual.r_long")),

    ("l", "l [wort]", SEITE, t("manual.l_short"),
     t("manual.l_long")),

    ("/", "/wort", SEITE, t("manual.slash_short"),
     t("manual.slash_long")),

    ("n", "n | n<nr>", NAVIGATION, t("manual.n_short"),
     t("manual.n_long")),

    ("fm", "fm [nr]", SEITE, t("manual.fm_short"),
     t("manual.fm_long")),

    ("rss", "rss [url]", SEITE, t("manual.rss_short"),
     t("manual.rss_long")),

    ("bu", "bu [r]", SEITE, t("manual.bu_short"),
     t("manual.bu_long")),

    ("we", "we [r]", SEITE, t("manual.we_short"),
     t("manual.we_long")),

    ("o", "o [nr]", SEITE, t("manual.o_short"),
     t("manual.o_long")),

    ("dl", "dl [nr]", ABLAGE, t("manual.dl_short"),
     t("manual.dl_long")),

    ("a", "a", ABLAGE, t("manual.a_short"),
     t("manual.a_long")),

    ("m", "m", ABLAGE, t("manual.m_short"),
     t("manual.m_long")),

    ("home", "home", NAVIGATION, t("manual.home_short"),
     t("manual.home_long")),

    ("h", "h [nr]", ABLAGE, t("manual.h_short"),
     t("manual.h_long")),

    ("sum", "sum", KI, t("manual.sum_short"),
     t("manual.sum_long")),

    ("ask", "ask <question>", KI, t("manual.ask_short"),
     t("manual.ask_long")),

    ("go", "go <text>", KI, t("manual.go_short"),
     t("manual.go_long")),

    ("chat", "chat [nr]", KI, t("manual.chat_short"),
     t("manual.chat_long")),

    ("log", "log [nr] | log del <nr> | log clear", KI, t("manual.log_short"),
     t("manual.log_long")),

    ("w", "w", KI, t("manual.w_short"),
     t("manual.w_long")),

    ("p", "p <nr>", KI, t("manual.p_short"),
     t("manual.p_long")),

    ("x", "x | x -", KI, t("manual.x_short"),
     t("manual.x_long")),

    ("ai", "ai | ai provider <name> | ai key <key> | ai model <name>", KI, t("manual.ai_short"),
     t("manual.ai_long")),

    ("u", "u | u reset", KI, t("manual.u_short"),
     t("manual.u_long")),

    ("fc", "fc", SYSTEM, t("manual.fc_short"),
     t("manual.fc_long")),

    ("c", "c", SYSTEM, t("manual.c_short"),
     t("manual.c_long")),

    ("i", "i", SYSTEM, t("manual.i_short"),
     t("manual.i_long")),

    ("t", "t", SYSTEM, t("manual.t_short"),
     t("manual.t_long")),

    ("sv", "sv", SYSTEM, t("manual.sv_short"),
     t("manual.sv_long")),

    ("game", "game [name]", SPIELE, t("manual.game_short"),
     t("manual.game_long")),

    ("paddle", "paddle", SPIELE, t("manual.pong_short"),
     t("manual.pong_long")),

    ("stacker", "stacker", SPIELE, t("manual.tetris_short"),
     t("manual.tetris_long")),

    ("snake", "snake", SPIELE, t("manual.snake_short"),
     t("manual.snake_long")),

    ("bricks", "bricks", SPIELE, t("manual.breakout_short"),
     t("manual.breakout_long")),

    ("dragon", "dragon", SPIELE, t("manual.dragon_short"),
     t("manual.dragon_long")),

    ("?", "? [befehl]", SYSTEM, t("manual.help_short"),
     t("manual.help_long")),

    ("up", "up", SYSTEM, t("manual.up_short"),
     t("manual.up_long")),

    ("q", "q", SYSTEM, t("manual.q_short"),
     t("manual.q_long")),
]

# Features without their own command — modes and automatic behaviors.
CONCEPTS = [
    ("hauptmenue", t("manual.concept_main_menu"), NAVIGATION, t("manual.concept_main_menu_short"),
     t("manual.concept_main_menu_long")),

    ("setzkasten", t("manual.concept_typecase"), SEITE, t("manual.concept_typecase_short"),
     t("manual.concept_typecase_long")),

    ("aria", t("manual.concept_aria"), SEITE, t("manual.concept_aria_short"),
     t("manual.concept_aria_long")),

    ("farbe", t("manual.concept_color"), SYSTEM, t("manual.concept_color_short"),
     t("manual.concept_color_long")),

    ("baud", t("manual.concept_baud"), SYSTEM, t("manual.concept_baud_short"),
     t("manual.concept_baud_long")),

    ("sound", t("manual.concept_sound"), SYSTEM, t("manual.concept_sound_short"),
     t("manual.concept_sound_long")),


    ("firecrawl", t("manual.concept_firecrawl"), SYSTEM, t("manual.concept_firecrawl_short"),
     t("manual.concept_firecrawl_long")),

    ("login", t("manual.concept_login"), SYSTEM, t("manual.concept_login_short"),
     t("manual.concept_login_long")),

    ("links-werkzeug", t("manual.concept_links_tool"), SYSTEM, t("manual.concept_links_tool_short"),
     t("manual.concept_links_tool_long")),
]

ALL = FEATURES + CONCEPTS
BY_KEY = {key: entry for entry in ALL for key in [entry[0]]}


def lookup(name):
    """Finds an entry by command, syntax, or keyword in the title."""
    q = (name or "").strip().lower()
    if not q:
        return None
    if q != "/":
        q = q.lstrip("/") or "/"
    if q in BY_KEY:
        return BY_KEY[q]
    for entry in ALL:
        key, syntax, _, kurz, _ = entry
        if q == key or q in syntax.lower().split() or q in kurz.lower():
            return entry
    return None


SYNTAX_COL = 28     # width of the command column in the box


def _section(title, rows, width):
    """A category as a CP437 box: title on the top edge, below it
    command and short description in two columns."""
    import textwrap

    inner = width - 4                      # '│ ' + content + ' │'
    desc_col = max(20, inner - SYNTAX_COL - 1)
    head = f"┌─[ {title} ]"
    out = [head + "─" * max(0, width - len(head) - 1) + "┐"]
    for syntax, kurz in rows:
        wrapped = textwrap.wrap(kurz, desc_col) or [""]
        if len(syntax) > SYNTAX_COL:       # long syntax gets its own line
            out.append(f"│ {syntax[:inner].ljust(inner)} │")
            first = ""
        else:
            first = syntax
        for i, part in enumerate(wrapped):
            left = first if i == 0 else ""
            out.append(f"│ {left:<{SYNTAX_COL}} {part:<{desc_col}} │")
    out.append("└" + "─" * (width - 2) + "┘")
    return out


def overview():
    """Categorized command overview as text (source for '?')."""
    from .constants import screen_width

    width = max(60, min(screen_width(), 100))
    title = t("manual.overview_title")
    out = ["",
           "╔" + "═" * (width - 2) + "╗",
           "║ " + title[:width - 4].ljust(width - 4) + " ║",
           "╚" + "═" * (width - 2) + "╝"]
    for category in (NAVIGATION, SEITE, ABLAGE, KI, SPIELE, SYSTEM):
        rows = [(s, k) for _, s, c, k, _ in FEATURES if c == category]
        if not rows:
            continue
        out.append("")
        out += _section(category.upper(), rows, width)
    out += [
        "",
        t("manual.overview_footer_1"),
        t("manual.overview_footer_2"),
        t("manual.overview_footer_3"),
        "",
    ]
    return "\n".join(out)


def overview_lines():
    """The overview as pager lines — each box is a group, so the page
    break doesn't fall in the middle of a frame."""
    from .constants import BOLD

    out, group = [], 0
    for line in overview().splitlines():
        if line.startswith(("╔", "╚", "║")):
            out.append((BOLD, line, "head"))
        elif line.startswith("┌"):
            group += 1
            out.append((BOLD, line, f"sec{group}"))
        elif line.startswith(("│", "└")):
            out.append((None, line, f"sec{group}"))
        else:
            out.append((None, line))
    return out


def explain(name):
    """Detailed explanation of a feature as text."""
    entry = lookup(name)
    if not entry:
        return None
    key, syntax, category, kurz, lang = entry
    return f"{syntax}  —  {kurz}\n[{category}]\n\n{lang}"


def catalog():
    """Complete catalog as text — the knowledge base for the SysOp."""
    lines = []
    for key, syntax, category, kurz, lang in ALL:
        lines.append(f"{key} | {syntax} | {category} | {kurz}\n{lang}\n")
    return "\n".join(lines)
