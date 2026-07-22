"""The mailbox's bulletin board, fed from any number of news sources.

A real board greeted its callers with the SysOp's bulletins. Here they come
from the sources configured under 'c' > Bulletins during the dial-in
sequence — as many as the caller likes, RSS feeds and plain news pages side
by side. An **RSS/Atom feed needs no AI at all**: an entry is already one
clean headline, so it becomes a bulletin as it stands, and the board works
without a key. Only a plain news page has to be read by the SysOp.

Turning those different shapes into one board is the job of `newsdesk`,
which normalises every source into the same entry and merges the lot by
publication date. What is left here: the cache, the cadence, and how the
result is presented.

The result lives in the database with a timestamp and is reused until the
cadence has run out (6 hours by default, 0 = every dial-up). Everything
happens in a background thread and stays silent: no key, no source, no
network, bad answer — the caller simply sees the built-in bulletins."""

import threading
import time

from . import db, newsdesk
from .i18n import t

SECTION = "bulletins"
CACHE_SECTION = "bulletins_cache"

DEFAULT_TTL_HOURS = 6
FEED_TTL_MINUTES = 5   # a feed costs nothing, so it may run hot
DEFAULT_COUNT = 5
MAX_COUNT = 12
MAX_SOURCES = 8        # more than this and the dial-in wait gets silly
PANEL_ITEMS = 3        # how many fit into the welcome box

_lock = threading.Lock()
_thread = None


# -- Configuration ---------------------------------------------------------


def config():
    cfg = db.get_section(SECTION)
    # "url" is what single-source setups stored before; newsdesk.normalize
    # folds it into the list, so an existing configuration just carries over.
    raw = cfg.get("sources", cfg.get("url", ""))
    return {
        "sources": newsdesk.normalize(raw),
        "ttl_hours": cfg.get("ttl_hours", DEFAULT_TTL_HOURS),
        "count": cfg.get("count", DEFAULT_COUNT),
    }


def save_config(cfg):
    cfg = dict(cfg)
    cfg["sources"] = newsdesk.normalize(cfg.get("sources"))
    cfg.pop("url", None)  # the legacy single source has been folded in
    db.set_section(SECTION, cfg)


def sources():
    return config()["sources"]


def active_urls():
    return newsdesk.enabled_urls(config()["sources"])


def configured():
    return bool(active_urls())


# -- Cache -----------------------------------------------------------------


def _signature(urls=None):
    """Which sources a cached board was built from. Changing, adding or
    switching off a source invalidates it — the mix would be a different
    board."""
    return "\n".join(active_urls() if urls is None else urls)


def cache():
    """The stored bulletins: {"sig", "ts", "items": [...]}.

    A board built from a different set of sources than the configured one is
    worthless — the caller changed the mix, so it counts as empty."""
    data = db.get_section(CACHE_SECTION)
    if not data.get("items") or data.get("sig") != _signature():
        return {}
    return data


def items():
    return cache().get("items", [])


def age_hours():
    ts = cache().get("ts", 0)
    return (time.time() - ts) / 3600 if ts else None


def from_feed():
    """True when every stored bulletin came straight from a feed — then no AI
    was involved and a refresh costs nothing but a little line time."""
    got = items()
    return bool(got) and all(e.get("kind", newsdesk.RSS) == newsdesk.RSS for e in got)


def ttl_hours():
    """The cadence that actually applies: a feed is free, so it refreshes
    every few minutes; a page has to be read by the SysOp and therefore
    keeps the configured cadence."""
    if from_feed():
        return FEED_TTL_MINUTES / 60
    return config()["ttl_hours"]


def stale():
    """True when the cache is missing or older than the applicable cadence.
    A cadence of 0 means every call fetches afresh."""
    age = age_hours()
    return age is None or age >= ttl_hours()


def clear():
    db.set_section(CACHE_SECTION, {})


# -- Generation ------------------------------------------------------------


def needs_ai():
    """True when the board can only be filled with an AI key — i.e. every
    known source is a plain page. With even one feed in the mix a refresh
    still delivers something, so it isn't blocked.

    Unknown before the first fetch, so an unvisited source counts as
    harmless."""
    got = items()
    return bool(got) and all(e.get("kind") == newsdesk.AI for e in got)


def generate(sysop):
    """Fetches every configured source and merges them into one dated board.
    Returns the list (possibly empty); never raises, never prints."""
    urls = active_urls()
    if not urls:
        return []
    count = max(1, min(MAX_COUNT, config()["count"]))
    try:
        result = newsdesk.collect(urls, sysop, count)
    except Exception:
        return []
    if result:
        db.set_section(CACHE_SECTION, {
            "sig": _signature(urls), "ts": time.time(), "items": result,
        })
    return result


def refresh(sysop, force=False):
    """Regenerates if the cache has expired (or `force`). One at a time."""
    if not _lock.acquire(blocking=False):
        return items()
    try:
        if not force and not stale():
            return items()
        return generate(sysop)
    finally:
        _lock.release()


def refresh_async(sysop):
    """Starts the refresh next to the dial-in sequence — the login types
    away for a few seconds, which is exactly the time this needs."""
    global _thread
    # A feed source works without a key — only a plain page needs the SysOp.
    if not configured() or not stale():
        return None
    if needs_ai() and not (sysop and sysop.has_key()):
        return None
    if _thread and _thread.is_alive():
        return _thread
    _thread = threading.Thread(target=_run, args=(sysop,), daemon=True)
    _thread.start()
    return _thread


def _run(sysop):
    try:
        refresh(sysop)
    except Exception:
        pass


def wait(seconds=2.0):
    """Gives a running refresh a moment — used right before the welcome box
    is drawn, so a nearly finished bulletin still makes it onto the screen."""
    if _thread and _thread.is_alive():
        _thread.join(seconds)


# -- Presentation ----------------------------------------------------------


def panel_texts(limit=PANEL_ITEMS):
    """The bulletin lines for the welcome box — [] without fresh news."""
    return [entry["text"] for entry in items()[:limit]]


def _source_label(data=None):
    """The board's dateline: which sources it was mixed from. One source
    names itself, several are counted — a header listing eight domains would
    push everything else off the line."""
    labels = []
    for url in active_urls():
        label = newsdesk.label_for(url)
        if label not in labels:
            labels.append(label)
    if not labels:
        return "-"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return " + ".join(labels)
    return t("bulletins.source_mixed", first=labels[0], rest=len(labels) - 1)


def entry_age(entry):
    """How old one bulletin is, as a short marker ("2 h", "5 min") — "" when
    the source gave no date. Mixed boards need it per line: the board as a
    whole is only as old as its last fetch, an entry can be days older."""
    ts = entry.get("ts")
    if not ts:
        return ""
    minutes = max(0, int((time.time() - ts) / 60))
    if minutes < 60:
        return t("bulletins.age_min", minutes=minutes)
    if minutes < 60 * 48:
        return t("bulletins.age_hour", hours=minutes // 60)
    return t("bulletins.age_day", days=minutes // (60 * 24))


def _entry_mark(entry):
    """Origin and age of a single bulletin, e.g. "srf.ch · 2 h"."""
    parts = [p for p in (entry.get("source", ""), entry_age(entry)) if p]
    return " · ".join(parts)


def _heading():
    """The board's headline — 'source' or 'sources', depending on the mix."""
    key = "bulletins.page_heading" if len(active_urls()) < 2 else "bulletins.page_heading_multi"
    return t(key, source=_source_label())


def _entry_lines(pg, text, bullet):
    """One bulletin as list lines: the follow-up lines are indented under
    the first, so the eye sees where one bulletin ends and the next starts.
    Wrapped here rather than by the renderer, which knows no hanging indent.
    "tight" keeps the blank lines out from between them."""
    import textwrap

    from .constants import screen_width

    width = max(40, screen_width())
    for line in textwrap.wrap(text, width, initial_indent=bullet,
                              subsequent_indent="  ") or [bullet.strip()]:
        pg.blocks.append({"type": "text", "tight": True, "content": line})


def board_rows(width=None):
    """The bulletins as lightbar rows plus the URL behind each one.

    Returns (rows, urls): `rows` are (key, label, value) tuples for
    lightbar.menu, `urls` maps the same key to the article's address —
    a bulletin without a link simply isn't in there."""
    from .constants import screen_width

    width = width or screen_width()
    entries = items()
    # " [ 1] " eats six columns, and on a mixed board the origin/age marker
    # on the right wants its own room — the widest one sets the column.
    marks = [_entry_mark(e) for e in entries]
    mark_w = max([len(m) for m in marks] or [0])
    label_w = max(20, width - 8 - (mark_w + 2 if mark_w else 0))
    rows, urls = [], {}
    for i, (entry, mark) in enumerate(zip(entries, marks), 1):
        key = str(i)
        rows.append((key, entry["text"][:label_w], mark))
        if entry.get("url"):
            urls[key] = entry["url"]
    return rows, urls


def age_line():
    """The dateline under the board: how old the bulletins are and when the
    next batch is due. A feed counts in minutes, a page in hours."""
    age = age_hours() or 0
    if from_feed():
        return t("bulletins.page_age_feed", minutes=int(age * 60),
                 ttl=FEED_TTL_MINUTES)
    ttl = config()["ttl_hours"]
    return t("bulletins.page_age" if ttl else "bulletins.page_age_instant",
             hours=int(age), ttl=ttl)


def board_subtitle():
    """Sources and age of the board — the menu's subtitle."""
    return "{}  ·  {}".format(_heading(), age_line())


def page():
    """All bulletins as a page: every headline carries the [n] link to the
    original article, so the board is a real entry point, not just a note."""
    from .page import Page

    entries = items()
    pg = Page("bbs://bulletins", t("bulletins.page_title"))
    pg.blocks.append({"type": "heading", "content": _heading()})
    if not entries:
        pg.blocks.append({"type": "text", "content": t("bulletins.page_empty")})
        return pg
    for entry in entries:
        num = pg.add_link(entry["url"], entry["title"]) if entry.get("url") else None
        marker = f" [{num}]" if num else ""
        _entry_lines(pg, f"{entry['text']}{marker}", "· ")
        # The headline only earns its own lines when the bulletin isn't
        # already that headline — with a feed source the two are identical.
        headline = (entry.get("title") or "").strip()
        if headline and headline.lower() not in entry["text"].strip().lower():
            _entry_lines(pg, headline, "  ")
        # Which of the mixed sources this line came from, and how old it is.
        mark = _entry_mark(entry)
        if mark:
            _entry_lines(pg, mark, "  ")
    pg.blocks.append({"type": "rule", "content": ""})
    pg.blocks.append({"type": "text", "content": age_line()})
    return pg
