"""Bulletin board submenus: sources, cadence and count.

Named like the top-level ``bbs_browser.bulletins`` module on purpose — the
data module is always imported as ``from .. import bulletins`` here, never
via a bare relative ``from . import bulletins``.
"""

from .. import lightbar
from ..i18n import t


def _bulletin_summary():
    """Short status of the bulletin board for its main menu row."""
    from .. import bulletins
    cfg = bulletins.config()
    if not bulletins.configured():
        return t("configmenu.not_set")
    age = bulletins.age_hours()
    # A feed source runs on its own short cadence, the configured one only
    # applies to a page the SysOp has to read.
    label = (t("configmenu.bulletins_ttl_feed", minutes=bulletins.FEED_TTL_MINUTES)
             if bulletins.from_feed() else _ttl_label(cfg["ttl_hours"]))
    if age is None:
        return t("configmenu.bulletins_pending", ttl=label)
    return t("configmenu.bulletins_state", count=len(bulletins.items()),
             hours=int(age), ttl=label)


def _ttl_label(hours):
    return (t("configmenu.bulletins_ttl_instant") if not hours
            else t("configmenu.bulletins_ttl_value", hours=hours))


def _source_kind_label(url):
    """What a configured source turned out to be, as far as the board knows:
    an RSS feed (free) or a page the SysOp has to read (costs a key). Before
    the first fetch nothing is known — and we don't go online to find out."""
    from .. import bulletins, newsdesk

    label = newsdesk.label_for(url)
    kinds = {e.get("kind") for e in bulletins.items() if e.get("source") == label}
    if not kinds:
        return ""
    if kinds == {newsdesk.RSS}:
        return t("configmenu.source_kind_rss")
    return t("configmenu.source_kind_ai")


def _bulletin_sources_menu(term):
    """The news sources the board is mixed from: any number of RSS feeds and
    news pages side by side. ENTER switches one off without losing it, 'a'
    adds one, 'x' throws it out."""
    from .. import bulletins, newsdesk

    def rows():
        out = []
        for i, src in enumerate(bulletins.sources(), 1):
            kind = _source_kind_label(src["url"])
            state = t("configmenu.on") if src["enabled"] else t("configmenu.off")
            out.append((str(i), newsdesk.label_for(src["url"]),
                        f"{state} · {kind}" if kind else state))
        if not out:
            out.append((None, t("configmenu.bulletins_sources_empty"), ""))
        out.append(("a", t("configmenu.bulletins_source_add"), ""))
        return out

    def save(sources):
        cfg = bulletins.config()
        cfg["sources"] = sources
        bulletins.save_config(cfg)
        # The mix defines the board — a changed set makes the cache a lie.
        bulletins.clear()

    def cycle(key, direction):
        """Left/right (and ENTER) switch a source off and on again."""
        if not key or not key.isdigit():
            return False
        srcs = bulletins.sources()
        idx = int(key) - 1
        if not 0 <= idx < len(srcs):
            return False
        srcs[idx]["enabled"] = not srcs[idx]["enabled"]
        save(srcs)
        return True

    def on_key(pressed, key):
        """'x' or DEL throws the marked source out for good."""
        if pressed not in ("x", "X", "d", "D") or not key or not key.isdigit():
            return False
        srcs = bulletins.sources()
        idx = int(key) - 1
        if not 0 <= idx < len(srcs):
            return False
        srcs.pop(idx)
        save(srcs)
        return True

    at = "a"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_bulletin_sources"), rows,
                               on_cycle=cycle, on_key=on_key, start=at,
                               hint=t("configmenu.bulletins_sources_hint"))
        if not choice:
            return
        at = choice
        if choice == "a":
            srcs = bulletins.sources()
            if len(srcs) >= bulletins.MAX_SOURCES:
                term.error(t("configmenu.bulletins_sources_full",
                             max=bulletins.MAX_SOURCES))
                continue
            url = term.prompt(t("configmenu.prompt_bulletins_url")).strip()
            if not url:
                continue
            srcs.append({"url": url, "enabled": True})
            before = len(srcs)
            srcs = newsdesk.normalize(srcs)  # drops it again if already there
            save(srcs)
            term.type_out(t("configmenu.bulletins_source_added", url=url)
                          if len(srcs) == before
                          else t("configmenu.bulletins_source_dupe"), delay=0.003)
        elif choice.isdigit():
            cycle(choice, 1)


def _bulletin_menu(term, sysop):
    """News source, cadence and number of the bulletins that greet the
    caller in the welcome box."""
    from .. import bulletins

    def rows():
        cfg = bulletins.config()
        n_on = len(bulletins.active_urls())
        n_all = len(cfg["sources"])
        return [
            ("1", t("configmenu.bulletins_sources"),
             t("configmenu.bulletins_sources_state", on=n_on, total=n_all)
             if n_all else t("configmenu.not_set")),
            ("2", t("configmenu.bulletins_ttl"), _ttl_label(cfg["ttl_hours"])),
            ("3", t("configmenu.bulletins_count"), str(cfg["count"])),
            ("4", t("configmenu.bulletins_refresh"), _bulletin_summary()),
            ("5", t("configmenu.bulletins_clear"), ""),
        ]

    def cycle(key, direction):
        cfg = bulletins.config()
        if key == "2":
            # 0 = every dial-up.
            cfg["ttl_hours"] = max(0, min(72, cfg["ttl_hours"] + direction))
        elif key == "3":
            cfg["count"] = max(1, min(bulletins.MAX_COUNT, cfg["count"] + direction))
        else:
            return False
        bulletins.save_config(cfg)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_bulletins"), rows,
                               on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        if choice == "1":
            _bulletin_sources_menu(term)
        elif choice == "4":
            if not bulletins.configured():
                term.error(t("bulletins.no_url"))
            elif bulletins.needs_ai() and not sysop.has_key():
                term.error(t("bulletins.no_key"))
            else:
                term.type_out(t("bulletins.fetching"), delay=0.003)
                fresh = bulletins.refresh(sysop, force=True)
                if fresh:
                    term.type_out(t("bulletins.refreshed", count=len(fresh)), delay=0.003)
                else:
                    term.error(t("bulletins.refresh_failed"))
        elif choice == "5":
            bulletins.clear()
            term.type_out(t("bulletins.cleared"), delay=0.003)
