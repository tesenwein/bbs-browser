"""Nostalgia: login sequence, caller counter, and ZMODEM 'downloads'."""

import getpass
import hashlib
import os
import re
import secrets
import sys
import textwrap
import time
from datetime import datetime

from . import boxes, keys, lightbar
from .constants import BOLD, DIM, RESET, screen_width
from .i18n import t
from .state import load_section, save_section
from .users import BAUD_RATES, MAX_NODE

DOWNLOAD_DIR = os.path.expanduser("~/bbs_downloads")


SYSTEM_NAME = "BBS-BROWSER"
SYSOP_NAME = "CLAUDE"   # Fallback as long as no AI key is configured


def _sysop_name(browser):
    """The SysOp is named after the model playing them: the first part of
    the name in uppercase ('claude-haiku-4-5' -> CLAUDE, 'gpt-4o-mini' -> GPT).
    A provider prefix like 'deepseek/...' does not count as a name part."""
    sysop = getattr(browser, "sysop", None) if browser else None
    model = sysop.model_name() if sysop else ""
    stem = model.rsplit("/", 1)[-1].split("-", 1)[0].strip().upper()
    return stem or SYSOP_NAME


_VERSION_CACHE = None


def _git_version():
    """Latest version from the source tree's git tags — '' if it can't be determined.

    The release CI does not commit the version bump back to main; the
    version 'travels' via tags. Anyone running from source therefore has an
    outdated number in pyproject/__init__ — the latest tag is the truth."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip().lstrip("vV")
    except Exception:
        pass
    return ""


def version():
    """Program version — not maintained in two places.

    Prefers the package metadata (correct for an installed wheel). If the
    program runs from the source tree, the metadata is missing and the
    embedded number is outdated — then the latest git tag is the truth,
    and only as a last resort does the fixed __version__ apply."""
    global _VERSION_CACHE
    if _VERSION_CACHE:
        return _VERSION_CACHE

    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        _VERSION_CACHE = _v("bbs-browser")
        return _VERSION_CACHE
    except PackageNotFoundError:
        pass
    except Exception:
        pass

    _VERSION_CACHE = _git_version()
    if _VERSION_CACHE:
        return _VERSION_CACHE

    from . import __version__
    _VERSION_CACHE = __version__
    return _VERSION_CACHE


def _update_hint():
    """Text for the main-menu hint when a newer release is in the cache."""
    try:
        from .update import update_hint
        newer = update_hint(version())
        return t("update.board_hint", version=newer) if newer else ""
    except Exception:
        return ""


def _get_weekdays():
    return (
        t("nostalgia.day_monday"),
        t("nostalgia.day_tuesday"),
        t("nostalgia.day_wednesday"),
        t("nostalgia.day_thursday"),
        t("nostalgia.day_friday"),
        t("nostalgia.day_saturday"),
        t("nostalgia.day_sunday"),
    )


def _get_bulletins():
    return [
        t("nostalgia.bulletin_1"),
        t("nostalgia.bulletin_2"),
        t("nostalgia.bulletin_3"),
        t("nostalgia.bulletin_4"),
        t("nostalgia.bulletin_5"),
        t("nostalgia.bulletin_6"),
        t("nostalgia.bulletin_7"),
    ]


def __getattr__(name):
    """Still allows `from .nostalgia import WEEKDAYS/BULLETINS` (e.g. in
    tests) — returns the lists in the currently configured language."""
    if name == "WEEKDAYS":
        return _get_weekdays()
    if name == "BULLETINS":
        return _get_bulletins()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _news_texts():
    """The AI bulletins for the welcome box — [] when nothing is stored."""
    try:
        from . import bulletins as news
        return news.panel_texts()
    except Exception:
        return []


def _weather_text():
    """The weather station's one-liner for the welcome box — "" when no
    place is configured or nothing has been fetched yet."""
    try:
        from . import weather
        return weather.panel_line()
    except Exception:
        return ""


def system_panel_lines(term, prof, last_call, browser=None):
    """The mailbox's welcome box as finished lines: system info,
    statistics, bulletin. Printed at login and then stays as the
    header of the main menu. The node line draws its numbers from
    the same session selection as the WHO list ('w'), so both
    tell the same story."""
    c = term.color
    inner = screen_width() - 4
    now = datetime.now()
    weekdays = _get_weekdays()
    bulletins = _get_bulletins()
    out = []

    def row(label, value):
        text = f" {label:<16}{value}"
        out.append(c + "║" + text[:inner + 2].ljust(inner + 2) + "║" + RESET)

    def divider(left="╟", right="╢"):
        out.append(c + boxes.double_divider(screen_width(), left, right) + RESET)

    out.append(c + boxes.double_top(screen_width()) + RESET)
    head = f" {SYSTEM_NAME} "
    out.append(c + "║" + BOLD + head.center(inner + 2) + RESET + c + "║" + RESET)
    divider()
    sysop = getattr(browser, "sysop", None) if browser else None
    if sysop and sysop.has_key():
        row(t("nostalgia.label_sysop"), _sysop_name(browser))
    row(t("nostalgia.label_software"), t(
        "nostalgia.software_desc", version=version(),
        nodes=MAX_NODE, baud=f"{min(BAUD_RATES)}-{max(BAUD_RATES)}"))
    hint = _update_hint()
    if hint:
        row(t("nostalgia.label_update"), hint)
    node = browser.node_idx + 1 if browser else 1
    callers = browser.users.online_count() if browser and browser.users else 0
    row(t("nostalgia.label_node"), t(
        "nostalgia.node_status" if callers else "nostalgia.node_status_alone",
        node=node, nodes=MAX_NODE, count=callers))
    row(t("nostalgia.label_time"), f"{weekdays[now.weekday()]}, {now.strftime('%d.%m.%Y  %H:%M')} {t('nostalgia.time_suffix')}")
    weather_line = _weather_text()
    if weather_line:
        row(t("nostalgia.label_weather"), weather_line)
    row(t("nostalgia.label_handle"), prof.get("handle", "?"))
    row(t("nostalgia.label_caller"), str(prof.get("caller_count", 1)))
    row(t("nostalgia.label_last_call"), last_call or t("nostalgia.first_call_msg"))
    row(t("nostalgia.label_timelimit"), t("nostalgia.timelimit_msg"))
    divider()
    # Fresh AI bulletins from the news source take precedence — only without
    # them does the box fall back to the built-in tips.
    news = _news_texts()
    shown = news or [bulletins[prof.get("caller_count", 1) % len(bulletins)]]
    label = t("nostalgia.label_news") if news else t("nostalgia.label_bulletin")
    out.append(c + "║" + BOLD + f" {label} ".ljust(inner + 2) + RESET + c + "║" + RESET)
    for bulletin in shown:
        for line in textwrap.wrap(bulletin, inner):
            out.append(c + "║ " + DIM + line.ljust(inner) + RESET + c + " ║" + RESET)
    out.append(c + boxes.double_bottom(screen_width()) + RESET)
    return out


# The "last call" shown at login — the welcome box in the main menu
# should display the same time, not the call currently in progress.
_last_call_shown = None


def system_screen(term, prof, last_call, browser=None):
    """The mailbox's welcome screen at login."""
    global _last_call_shown
    _last_call_shown = last_call
    for line in system_panel_lines(term, prof, last_call, browser):
        print(line)


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()


def verify_password(prof, password):
    """Checks a plaintext password against the hash stored in the profile."""
    stored = prof.get("pw_hash")
    if not stored:
        return True
    candidate = _hash_password(password, prof.get("pw_salt", ""))
    return secrets.compare_digest(candidate, stored)


def _ask_password(term, label):
    """Hidden password entry in terminal style."""
    return getpass.getpass(term.color + BOLD + label + RESET + term.color)


def change_password(term):
    """Set, change, or remove the password (empty input = none)."""
    prof = load_section("profile")
    if prof.get("pw_hash"):
        try:
            current = _ask_password(term, t("nostalgia.pw_current_prompt"))
        except KeyboardInterrupt:
            term.on_interrupt()  # cancels the change; twice in a row hangs up
            return
        except EOFError:
            print()
            return
        if not verify_password(prof, current):
            term.error(t("nostalgia.password_wrong"))
            return
    try:
        new = _ask_password(term, t("nostalgia.pw_new_prompt"))
        if new:
            repeat = _ask_password(term, t("nostalgia.pw_repeat_prompt"))
            if new != repeat:
                term.error(t("nostalgia.pw_mismatch"))
                return
    except KeyboardInterrupt:
        term.on_interrupt()
        return
    except EOFError:
        print()
        return
    if new:
        salt = secrets.token_hex(16)
        prof["pw_salt"] = salt
        prof["pw_hash"] = _hash_password(new, salt)
        term.type_out(t("nostalgia.pw_set"), delay=0.003)
    else:
        prof.pop("pw_hash", None)
        prof.pop("pw_salt", None)
        term.type_out(t("nostalgia.pw_removed"), delay=0.003)
    save_section("profile", prof)


def change_handle(term):
    """Change the handle (username) — empty input leaves everything as is."""
    prof = load_section("profile")
    term.type_out(t("nostalgia.handle_current", handle=prof.get("handle") or "-"), delay=0.003)
    try:
        # Ctrl+C is already handled inside term.prompt (cancel + ask), which
        # returns "" — that lands on "unchanged" below. Only EOF gets here.
        neu = term.prompt(t("nostalgia.handle_new_prompt")).strip()
    except EOFError:
        print()
        return
    if not neu:
        term.type_out(t("nostalgia.handle_unchanged"), delay=0.003)
        return
    prof["handle"] = neu.upper()[:20]
    save_section("profile", prof)
    term.type_out(t("nostalgia.handle_changed", handle=prof["handle"]), delay=0.003)


def _hangup(term):
    from .terminal import signoff
    term.type_out("\n+++ATH", delay=0.003)
    term.type_out("NO CARRIER", delay=0.003)
    term.type_out(signoff(), delay=0.0005)
    raise SystemExit(0)


def _password_gate(term, prof):
    """Real password prompt: three attempts, then the call is dropped.

    Ctrl+C asks here too instead of dropping the call straight away: the
    first press only cancels the entry, the second hangs up (on_interrupt).
    A cancelled entry doesn't burn one of the three attempts — only a wrong
    password does. Real end of input (EOF) still ends the call."""
    attempt = 0
    while attempt < 3:
        try:
            entered = _ask_password(term, t("nostalgia.password_prompt"))
        except KeyboardInterrupt:
            term.on_interrupt()
            continue
        except EOFError:
            _hangup(term)
        term.interrupts = 0
        if verify_password(prof, entered):
            term.type_out(t("nostalgia.access_granted_msg"), delay=0.006)
            return
        term.error(t("nostalgia.password_wrong"))
        attempt += 1
    _hangup(term)


def board_follows(term, browser):
    """True when the main board takes over right after the login AND shows
    the welcome box as its header — then the login must not print the box
    itself, otherwise the caller would see the same panel twice."""
    return keys.available() and bool(_board_header(term, browser)[0])


def login(term, browser=None, board=False):
    """Dial-in dialog: prompt for handle, password prompt, welcome screen.

    `board=True` means the main board follows: it draws the very same
    welcome box as its header, so the login only records the last call
    instead of printing the box a second time."""
    prof = load_section("profile")
    neu = not prof.get("handle")

    term.type_out("", delay=0)
    if neu:
        term.type_out(t("nostalgia.new_caller_msg"), delay=0.004)
        handle = term.prompt(t("nostalgia.handle_prompt")).strip() or "GAST"
        prof["handle"] = handle.upper()[:20]
        term.type_out(t("nostalgia.handle_registered_msg", handle=prof['handle']), delay=0.004)
    else:
        term.type_out(t("nostalgia.login_msg", handle=prof['handle']), delay=0.006)
        if prof.get("pw_hash"):
            _password_gate(term, prof)
        else:
            # No real password — just the familiar look of the asterisks.
            sys.stdout.write(term.color + BOLD + t("nostalgia.password_prompt") + RESET + term.color)
            sys.stdout.flush()
            for _ in range(8):
                sys.stdout.write("*")
                sys.stdout.flush()
                term.sleep(0.07 if not term.fast else 0)
            print(RESET)
            term.type_out(t("nostalgia.access_granted_msg"), delay=0.006)

    prof["caller_count"] = prof.get("caller_count", 0) + 1
    last = prof.get("last_call")
    prof["last_call"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    save_section("profile", prof)

    term.sleep(0.25 if not term.fast else 0)
    # The bulletins started with the dial-in; give them the last moment
    # before the welcome box goes to screen.
    if not term.fast:
        try:
            from . import bulletins as news
            news.wait()
        except Exception:
            pass
    try:
        from . import weather
        weather.wait()
    except Exception:
        pass
    if board and board_follows(term, browser):
        global _last_call_shown
        _last_call_shown = last
    else:
        system_screen(term, prof, last, browser)


def recent_entries(history, limit=8):
    """Most recent visits, newest first, without duplicates."""
    seen, out = set(), []
    for entry in reversed(history):
        if entry["url"] in seen:
            continue
        seen.add(entry["url"])
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def main_board(term, browser):
    """BBS main menu: the welcome box plus everything reachable from it.

    With a controllable terminal this is a single screen: the same panel
    the caller knows from the login, and below it one selectable list of
    built-in areas, favorites and recent visits. Favorites and history are
    trimmed to whatever still fits, so the board never scrolls. The chosen
    command is returned (ESC = nothing, proceeds with the normal command
    line). Without a controllable terminal the classic two-column board
    for typing in the number remains."""
    if keys.available():
        return _board_lightbar(term, browser)
    command = _board_table(term, browser.bookmarks[:8], recent_entries(browser.history, 8))
    _board_status(term, browser)
    return command


def _banner_lines():
    """The intro logo as a header for the main menu — the lightbar menu
    takes over the screen, otherwise the banner would vanish right after login."""
    from .terminal import banner

    return [line for line in banner().split("\n") if line.strip()]


# The chrome around the registers: menu box (3), their own frame (2), footer
# (2) and the status lines printed below the board (3).
_BOARD_CHROME = 10
_MIN_ROWS = 3      # below this the header has to give way


def _board_header(term, browser):
    """The welcome box (and the banner above it, if there is room) as the
    menu header — plus the number of list rows that fit below it.

    The box is what the caller knows from the login, so it stays as long
    as possible: first the banner goes, then the lists shrink, and only on
    a really cramped screen the box itself is dropped."""
    import shutil

    avail = shutil.get_terminal_size((80, 24)).lines
    prof = load_section("profile")
    banner = _banner_lines()
    panel = system_panel_lines(term, prof, _last_call_shown, browser)
    # The banner is a luxury: it only stays when the list keeps a decent
    # length despite it.
    chrome = _BOARD_CHROME + len(_board_areas())
    for head, needed in ((banner + panel, 2 * _MIN_ROWS), (panel, _MIN_ROWS), ([], 0)):
        free = avail - len(head) - chrome
        if free >= needed:
            return head, max(_MIN_ROWS, free)
    return [], _MIN_ROWS


def _board_lightbar(term, browser):
    """One panel: the welcome box, below it the two registers side by side —
    favorites left, recent visits right. The areas of the mailbox itself
    (chat, game, rss, w, c, ?) stay on the command line and in the handbook."""
    head, view = _board_header(term, browser)
    # Whatever is left below the welcome box is the height of the two
    # register columns. At most eight rows each: longer registers belong
    # in 'm' and 'h'.
    rows_free = min(8, max(2, view))
    favs = browser.bookmarks[:rows_free]
    recents = recent_entries(browser.history, rows_free)

    # " [ 1] " eats six columns of a half-width column.
    label_w = max(8, (screen_width() - 3) // 2 - 7)
    left = [(str(i), b["title"][:label_w], "") for i, b in enumerate(favs, 1)] \
        or [(None, t("nostalgia.no_bookmarks")[:label_w], "")]
    right = [(f"h{i}", e["title"][:label_w], "") for i, e in enumerate(recents, 1)] \
        or [(None, t("nostalgia.no_history")[:label_w], "")]

    titles = (t("nostalgia.header_bookmarks"), t("nostalgia.header_recent"))
    areas = _board_areas()
    if not favs and not recents and not areas:
        # Nothing to select yet (first call): the panel would fall straight
        # through to the command line — so print it plainly instead.
        for line in head + lightbar.pane_lines(term, (left, right), titles, 0, -1):
            print(line)
        _board_status(term, browser)
        return None

    choice = lightbar.menu(term, t("nostalgia.board_title"), areas,
                           hint=t("nostalgia.board_hint"), header=head,
                           panes=(left, right), pane_titles=titles)
    _board_status(term, browser)
    if not choice:
        return None
    if choice in ("bu", "we"):
        return choice
    # The chosen key becomes the command that the command loop executes.
    return f"h {choice[1:]}" if choice.startswith("h") else f"d {choice}"


def _board_areas():
    """Selectable areas above the two registers — each only appears once it
    actually has something to show."""
    areas = []
    try:
        from . import bulletins as news
        count = len(news.items())
    except Exception:
        count = 0
    if count:
        areas.append(("bu", t("nostalgia.area_bulletins"),
                      t("nostalgia.area_bulletins_count", count=count)))
    weather_line = _weather_text()
    if weather_line:
        areas.append(("we", t("nostalgia.area_weather"), weather_line))
    return areas


def _board_table(term, favs, recents):
    col_l = (screen_width() - 3) // 2
    col_r = screen_width() - 3 - col_l

    def cell(text, width):
        return (" " + text)[:width].ljust(width)

    rows_l = [f"[{i:>2}] {b['title']}" for i, b in enumerate(favs, 1)] or [t("nostalgia.no_bookmarks")]
    rows_r = [f"[{i:>2}] {e['title']}" for i, e in enumerate(recents, 1)] or [t("nostalgia.no_history")]

    c = term.color
    print(c + boxes.split_top(col_l, col_r, t("nostalgia.header_bookmarks"), t("nostalgia.header_recent")) + RESET)
    for row in range(max(len(rows_l), len(rows_r))):
        left = rows_l[row] if row < len(rows_l) else ""
        right = rows_r[row] if row < len(rows_r) else ""
        print(c + "│" + cell(left, col_l) + "│" + DIM + cell(right, col_r) + RESET + c + "│" + RESET)
    print(c + boxes.split_bottom(col_l, col_r) + RESET)
    return None


def _board_status(term, browser):
    prof = load_section("profile")
    c = term.color
    hint = _update_hint()
    if hint:
        print(c + BOLD + f"  » {hint}" + RESET)

    status = t("nostalgia.status_line",
               handle=prof.get('handle', 'GAST'),
               caller_num=prof.get('caller_count', 1),
               node=browser.node_idx + 1,
               bookmarks=len(browser.bookmarks),
               history=len(browser.history))
    term.status_bar(status)
    print(c + DIM + f"  {t('nostalgia.command_help')}" + RESET)


def safe_filename(name, ext=".txt"):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:48] or "download"
    return stem if stem.lower().endswith(ext) else stem + ext


def zmodem_download(term, filename, data):
    """Saves data to ~/bbs_downloads/ — with a ZMODEM retro progress bar."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    path = os.path.join(DOWNLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)

    total = max(1, len(data))
    cps = max(235, (getattr(term, "baud", 0) or 28800) // 10)
    bar_w = min(30, screen_width() - 40)
    steps = 24
    term.type_out(t("nostalgia.download_msg", filename=filename, size=total), delay=0.003)
    for i in range(1, steps + 1):
        pct = int(100 * i / steps)
        done = int(bar_w * i / steps)
        bar = "▓" * done + "░" * (bar_w - done)
        print(term.color + f"\r  {bar} {pct:3d}%  {cps} CPS  {t('nostalgia.errors')}: 0" + RESET, end="", flush=True)
        time.sleep(min(0.08, total / cps / steps))
    print()
    term.type_out(t("nostalgia.transfer_complete", path=path), delay=0.003)
    return path
