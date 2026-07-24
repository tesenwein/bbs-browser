"""Interactive configuration menu (command 'k') — nested by topic.

All submenus run through the same lightbar component: cursor up/down
selects, left/right toggles the row's value directly, Enter opens or
advances — and the old numeric hotkeys still work unchanged.
"""

from urllib.parse import urlparse

from . import colors, db, headers, i18n, lightbar
from .constants import (AMBER, GREEN, HEADER_MODES, IMG_SETTINGS, RESET, DIM,
                        invalidate_layout, screen_width)
from .i18n import t
from .firecrawl import FIRECRAWL_CLOUD, firecrawl_check, firecrawl_reset
from .fetch import normalize_base_url
from .state import (clear_sections, load_section, save_section, set_ui,
                    toggle_ui)

from .menukit import cycle as _cycle
from .menukit import mask as _mask
from .menukit import onoff as _onoff
from .menukit import status_tag as _status_tag

BAUD_RATES = (0, 2400, 9600)
COLOR_MODES = ("amber", "green", "auto", "multi")


def _confirm(term, key):
    return term.confirm(t(key))


def _reset_display(term, browser):
    """Anzeige-Einstellungen auf den Auslieferungszustand zuruecksetzen:
    Sektion loeschen (dann greifen wieder die Lade-Defaults) und dieselben
    Werte auf die laufenden Objekte anwenden."""
    clear_sections("ui")
    browser.images = "blocks"
    browser.img_width = 60
    browser.header = "logo"
    browser.auto_template = False
    browser.saver_idle = 300
    browser.color_auto = False
    colors.set_multi(False)
    term.color = AMBER
    term.fast = False
    term.baud = 9600
    term.sound = False
    i18n.set_lang(i18n.DEFAULT_LANG)
    invalidate_layout()


def _reset_all(term, browser):
    """Alle unkritischen Einstellungen zuruecksetzen — API-Keys, Passwort,
    Handle und MCP-Server bleiben unangetastet."""
    from . import bulletins, weather

    _reset_display(term, browser)
    clear_sections(bulletins.SECTION, bulletins.CACHE_SECTION,
                   weather.SECTION, weather.CACHE_SECTION, "shell")


def run_firecrawl_check(term, fc, ai_key):
    # A manual check is an explicit "try again" — clear the session mute.
    firecrawl_reset()
    term.rule(t("configmenu.firecrawl_check_title"))
    term.type_out(t("configmenu.firecrawl_checking"), delay=0.003)
    for status, msg in firecrawl_check(fc, ai_key):
        tag = _status_tag(status)
        style = "" if status == "OK" else DIM
        print(term.color + style + f"  {tag} {msg}" + RESET)
    term.rule()
    term.pause()


def config_menu(term, browser, sysop):
    def rows():
        prof = load_section("profile")
        pw_state = t("configmenu.pw_set_tag") if prof.get("pw_hash") else t("configmenu.not_set")
        return [
            ("1", t("configmenu.item_ai_sysop"), t("configmenu.item_ai_sysop_desc")),
            ("2", "Firecrawl", t("configmenu.item_firecrawl_desc")),
            ("3", t("configmenu.item_display"), t("configmenu.item_display_desc")),
            ("4", t("configmenu.item_password"), pw_state + "  " + t("configmenu.item_password_desc")),
            ("5", t("configmenu.item_handle"),
             (prof.get("handle") or "-") + "  " + t("configmenu.item_handle_desc")),
            ("6", t("configmenu.item_shell"),
             _shell_mode_label() + "  " + t("configmenu.item_shell_desc")),
            ("7", "MCP", _mcp_count_label() + "  " + t("configmenu.item_mcp_desc")),
            ("8", t("configmenu.item_weather"), _weather_summary()),
            ("9", t("configmenu.bulletins"), _bulletin_summary()),
            # Reset sits on '0', not '10': a two-character key would make '1'
            # ambiguous and cost every entry its instant hotkey.
            ("0", t("configmenu.item_reset"), t("configmenu.item_reset_desc")),
        ]

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_main"), rows, start=at)
        if not choice:
            return
        at = choice
        if choice == "1":
            _ai_menu(term, browser, sysop)
        elif choice == "2":
            _firecrawl_menu(term, browser)
        elif choice == "3":
            _display_menu(term, browser)
        elif choice == "4":
            from .nostalgia import change_password
            change_password(term)
        elif choice == "5":
            from .nostalgia import change_handle
            change_handle(term)
        elif choice == "6":
            _shell_menu(term)
        elif choice == "7":
            _mcp_menu(term)
        elif choice == "8":
            _weather_menu(term)
        elif choice == "9":
            _bulletin_menu(term, sysop)
        elif choice == "0":
            if _confirm(term, "configmenu.reset_all_confirm"):
                _reset_all(term, browser)
                term.type_out(t("configmenu.reset_done"), delay=0.003)
        else:
            term.error(t("configmenu.invalid_choice"))


def _prompt_preview(ai):
    """Short preview of the default prompt for the menu row."""
    text = " ".join((ai.get("prompt") or "").split())
    if not text:
        return t("configmenu.not_set")
    return (text[:37] + "…") if len(text) > 38 else text


def _ai_menu(term, browser, sysop):
    from .sysop_config import (PROVIDERS, active_provider, config_key,
                               provider_label, set_config_key)

    def rows():
        ai = load_section("ai")
        provider = active_provider(ai)
        return [
            ("1", t("configmenu.provider"), provider_label(provider)),
            ("2", t("configmenu.api_key"), _mask(config_key(ai, provider))),
            ("3", t("configmenu.model"), ai.get("model") or t("configmenu.model_default")),
            ("4", t("configmenu.sysop_prompt"), _prompt_preview(ai)),
            ("5", t("configmenu.templates"), _template_summary()),
        ]

    def cycle(key, direction):
        if key == "1":
            ai = load_section("ai")
            ai["provider"] = _cycle(PROVIDERS, active_provider(ai), direction)
            save_section("ai", ai)
            sysop._client = None
        else:
            return False
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_ai"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        ai = load_section("ai")
        provider = active_provider(ai)
        if choice == "2":
            set_config_key(ai, provider, term.prompt(t("configmenu.prompt_api_key")).strip())
            save_section("ai", ai)
            sysop._client = None
        elif choice == "3":
            ai["model"] = term.prompt(t("configmenu.prompt_model"))
            save_section("ai", ai)
            sysop._client = None
        elif choice == "4":
            current = (ai.get("prompt") or "").strip()
            if current:
                term.type_out(t("configmenu.sysop_prompt_current", prompt=current), delay=0.002)
            text = term.prompt(t("configmenu.prompt_sysop_prompt")).strip()
            if text == "-":
                ai.pop("prompt", None)
                save_section("ai", ai)
                term.type_out(t("configmenu.sysop_prompt_cleared"), delay=0.003)
            elif text:
                ai["prompt"] = text
                save_section("ai", ai)
                term.type_out(t("configmenu.sysop_prompt_saved"), delay=0.003)
        elif choice == "5":
            _template_menu(term, browser)
        else:
            term.error(t("configmenu.invalid_choice"))


def _bulletin_summary():
    """Short status of the bulletin board for its main menu row."""
    from . import bulletins
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
    from . import bulletins, newsdesk

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
    from . import bulletins, newsdesk

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
    from . import bulletins

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


def _template_summary():
    """Short status for the AI menu row: how many domains carry a learned
    style template, and whether the automatic mode is on."""
    n = len(db.templates())
    auto = load_section("ui").get("auto_template", False)
    if not n:
        return t("configmenu.templates_auto_only" if auto else "configmenu.not_set")
    return t("configmenu.templates_summary", n=n,
             auto=t("configmenu.on" if auto else "configmenu.off"))


def _template_menu(term, browser):
    """Learned style templates: toggle the auto-LEARNING, delete a single
    domain's template, or throw them all away. Applying is not a setting —
    a stored template is always used where it grips; the switch here only
    decides whether unknown domains get one learned on first visit.
    Building/refreshing happens with 'x' on the page itself — that's where
    the document is."""
    def rows():
        stored = db.templates()
        rows = [("a", t("configmenu.templates_autolearn"),
                 _onoff(browser.auto_template)),
                (None, t("configmenu.templates_always_used"), "")]
        for i, tpl in enumerate(stored, 1):
            rows.append((str(i), tpl["domain"],
                         t("configmenu.templates_row_hint", n=tpl["verified"])))
        if stored:
            rows.append(("0", t("configmenu.templates_clear"), ""))
        return rows

    at = "a"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_templates"), rows, start=at)
        if not choice:
            return
        at = choice
        if choice == "a":
            browser.auto_template = toggle_ui("auto_template", browser.auto_template)
            continue
        templates = db.templates()
        if choice == "0":
            if templates and _confirm(term, "configmenu.templates_clear_confirm"):
                db.template_clear()
                term.type_out(t("configmenu.templates_cleared"), delay=0.003)
            continue
        idx = int(choice) - 1 if choice.isdigit() else -1
        if not (0 <= idx < len(templates)):
            term.error(t("configmenu.invalid_choice"))
            continue
        domain = templates[idx]["domain"]
        if term.confirm(t("configmenu.templates_delete_confirm", domain=domain)):
            db.template_delete(domain)
            term.type_out(t("configmenu.templates_deleted", domain=domain), delay=0.003)
            # The numbering shifts after a delete — back to a stable anchor.
            at = "a"


def _weather_summary():
    """Short status of the weather station for the main menu row."""
    from . import weather
    cfg = weather.config()
    clocks = len(cfg["clocks"])
    if not weather.configured():
        return t("configmenu.weather_no_place", clocks=clocks)
    line = weather.panel_line()
    return line or t("configmenu.weather_pending", place=cfg["place"])


def _weather_menu(term):
    """Location, units and world clocks of the weather station — the one
    place where the caller sets up what greets him in the welcome box."""
    from . import weather

    def rows():
        cfg = weather.config()
        clocks = ", ".join(z.rsplit("/", 1)[-1].replace("_", " ")
                           for z in cfg["clocks"]) or t("configmenu.not_set")
        return [
            ("1", t("configmenu.weather_place"), cfg["place"] or t("configmenu.not_set")),
            ("2", t("configmenu.weather_units"), t("configmenu.weather_units_" + cfg["units"])),
            ("3", t("configmenu.weather_clocks"), clocks),
            ("4", t("configmenu.weather_clock_remove"), ""),
            ("5", t("configmenu.weather_refresh"), _weather_summary()),
        ]

    def cycle(key, direction):
        if key != "2":
            return False
        cfg = weather.config()
        cfg["units"] = _cycle(("metric", "imperial"), cfg["units"], direction or 1)
        weather.save_config(cfg)
        weather.clear()
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_weather"), rows,
                               on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        if choice == "1":
            _weather_place_prompt(term)
        elif choice == "3":
            zone = term.prompt(t("configmenu.prompt_weather_clock")).strip()
            if not zone:
                continue
            if weather.add_clock(zone):
                term.type_out(t("weather.clock_added", zone=zone), delay=0.003)
            else:
                term.error(t("weather.clock_invalid"))
        elif choice == "4":
            zones = weather.config()["clocks"]
            if not zones:
                continue
            picked = lightbar.menu(term, t("configmenu.title_weather_clocks"),
                                   [(z, z, "") for z in zones])
            if picked and weather.remove_clock(picked):
                term.type_out(t("weather.clock_removed", zone=picked), delay=0.003)
        elif choice == "5":
            if not weather.configured():
                term.error(t("weather.no_place"))
            else:
                term.type_out(t("weather.fetching"), delay=0.003)
                if weather.refresh(force=True):
                    term.type_out(weather.panel_line(), delay=0.003)
                else:
                    term.error(t("weather.refresh_failed"))


def _weather_place_prompt(term):
    """Place search: type a name, pick from the hits — '-' clears the place."""
    from . import weather
    query = term.prompt(t("configmenu.prompt_weather_place")).strip()
    if not query:
        return
    if query == "-":
        weather.clear_place()
        term.type_out(t("weather.place_cleared"), delay=0.003)
        return
    term.type_out(t("weather.searching"), delay=0.003)
    hits = weather.geocode(query)
    if not hits:
        term.error(t("weather.search_empty"))
        return
    rows = [(str(i), label, "") for i, (label, _, _, _) in enumerate(hits, 1)]
    choice = lightbar.menu(term, t("configmenu.title_weather_place"), rows)
    if not choice:
        return
    label, lat, lon, tz = hits[int(choice) - 1]
    weather.set_place(label, lat, lon, tz)
    term.type_out(t("weather.place_saved", place=label), delay=0.003)
    weather.refresh(force=True)


def _shell_mode_label():
    from .sysop_config import shell_config
    return t("configmenu.shell_mode_" + shell_config()[0])


def _shell_menu(term):
    """SysOp's system access: off / with confirmation / free, plus timeout."""
    from .sysop_config import SHELL_MODES, shell_config

    def rows():
        mode, timeout = shell_config()
        return [
            ("1", t("configmenu.shell_mode"), t("configmenu.shell_mode_" + mode)),
            ("2", t("configmenu.shell_timeout"), t("configmenu.shell_timeout_value", seconds=timeout)),
        ]

    def cycle(key, direction):
        if key != "1":
            return False
        shell = load_section("shell")
        shell["mode"] = _cycle(SHELL_MODES, shell_config()[0], direction)
        save_section("shell", shell)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_shell"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if choice == "1":
            # Only warn when switching it on — 'free' runs without any confirmation.
            cycle(choice, 1)
            if shell_config()[0] == "free":
                term.type_out(t("configmenu.shell_free_warning"), delay=0.003)
            continue
        if choice == "2":
            def _timeout(v):
                shell = load_section("shell")
                shell["timeout"] = max(1, v)
                save_section("shell", shell)
            _ask_number(term, t("configmenu.prompt_shell_timeout"), _timeout)
        else:
            term.error(t("configmenu.invalid_choice"))


# -- MCP servers ----------------------------------------------------------
#
# A list of custom MCP servers that the SysOp gets in addition to its
# internal tools. The first level shows the list, the second level
# maintains a single entry (URL, method, token or OAuth login).


def _mcp_count_label():
    from . import mcp
    servers = mcp.load_servers()
    if not servers:
        return t("configmenu.not_set")
    return t("configmenu.mcp_count", active=len(mcp.enabled_servers()), total=len(servers))


def _mcp_status_label(server):
    from . import mcp
    return t("configmenu.mcp_status_" + mcp.status(server))


def _mcp_menu(term):
    from . import mcp

    def rows():
        out = []
        for i, server in enumerate(mcp.load_servers(), 1):
            flag = "" if server.get("enabled", True) else t("configmenu.mcp_off_tag") + " "
            out.append((str(i), server.get("name", "?"),
                        flag + _mcp_status_label(server) + "  " + server.get("url", "")))
        out.append((None, t("configmenu.mcp_section_new"), ""))
        out.append(("n", t("configmenu.mcp_add"), t("configmenu.mcp_add_desc")))
        return out

    def toggle(key, _direction):
        servers = mcp.load_servers()
        if not key.isdigit() or not 1 <= int(key) <= len(servers):
            return False
        server = servers[int(key) - 1]
        server["enabled"] = not server.get("enabled", True)
        mcp.upsert(server)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_mcp"), rows, on_cycle=toggle,
                               start=at, hint=t("configmenu.mcp_hint"))
        if not choice:
            return
        at = choice
        if choice == "n":
            name = _mcp_add(term)
            if name:
                _mcp_server_menu(term, name)
            continue
        servers = mcp.load_servers()
        if choice.isdigit() and 1 <= int(choice) <= len(servers):
            _mcp_server_menu(term, servers[int(choice) - 1]["name"])
        else:
            term.error(t("configmenu.invalid_choice"))


def _mcp_add(term):
    """Asks for URL and name and creates the entry. Returns the name."""
    from urllib.parse import urlparse

    from . import mcp
    url = term.prompt(t("configmenu.prompt_mcp_url")).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    suggestion = mcp.unique_name(urlparse(url).netloc.removeprefix("www.").split(".")[0])
    name = mcp.unique_name(term.prompt(t("configmenu.prompt_mcp_name", name=suggestion)).strip()
                           or suggestion)
    mcp.upsert({"name": name, "url": url, "auth": "none", "enabled": True})
    return name


def _mcp_server_menu(term, name):
    from . import mcp

    def rows():
        server = mcp.find(name) or {}
        auth = server.get("auth", "none")
        token = t("configmenu.mcp_token_set") if server.get("token") else t("configmenu.not_set")
        return [
            ("1", t("configmenu.mcp_url"), server.get("url", "")),
            ("2", t("configmenu.mcp_auth"), t("configmenu.mcp_auth_" + auth)),
            ("3", t("configmenu.mcp_token") if auth == "bearer" else t("configmenu.mcp_login"),
             token if auth != "none" else t("configmenu.mcp_auth_none")),
            ("4", t("configmenu.mcp_active"), _onoff(server.get("enabled", True))),
            ("5", t("configmenu.mcp_test"), _mcp_status_label(server)),
            ("6", t("configmenu.mcp_logout"), t("configmenu.mcp_logout_desc")),
            ("7", t("configmenu.mcp_delete"), ""),
        ]

    def cycle(key, direction):
        server = mcp.find(name)
        if not server:
            return False
        if key == "2":
            server["auth"] = _cycle(mcp.AUTH_MODES, server.get("auth", "none"), direction)
        elif key == "4":
            server["enabled"] = not server.get("enabled", True)
        else:
            return False
        mcp.upsert(server)
        return True

    at = "1"
    while True:
        server = mcp.find(name)
        if not server:
            return
        choice = lightbar.menu(term, t("configmenu.title_mcp_server", name=name), rows,
                               on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        server = mcp.find(name)
        if choice == "1":
            server["url"] = term.prompt(t("configmenu.prompt_mcp_url")).strip() or server["url"]
            mcp.upsert(server)
        elif choice == "3":
            if server.get("auth") == "bearer":
                server["token"] = term.prompt(t("configmenu.prompt_mcp_token")).strip()
                mcp.upsert(server)
            elif server.get("auth") == "oauth":
                _mcp_login(term, server)
            else:
                term.type_out(t("configmenu.mcp_auth_none_hint"), delay=0.003)
                term.pause()
        elif choice == "5":
            term.type_out(t("configmenu.mcp_testing"), delay=0.003)
            ok, reason = mcp.probe(server)
            if ok:
                term.type_out(t("configmenu.mcp_test_ok"), delay=0.003)
            else:
                term.error(t("configmenu.mcp_test_failed", reason=reason))
            term.pause()
        elif choice == "6":
            mcp.logout(server)
            term.type_out(t("configmenu.mcp_logged_out"), delay=0.003)
            term.pause()
        elif choice == "7":
            if term.prompt(t("configmenu.mcp_delete_confirm", name=name)).lower() in ("j", "y"):
                mcp.remove(name)
                return
        else:
            term.error(t("configmenu.invalid_choice"))


def _mcp_login(term, server):
    """OAuth login with progress messages on the terminal."""
    from . import mcp

    def notify(step, **kwargs):
        term.type_out(t("configmenu.mcp_oauth_" + step, **kwargs), delay=0.002)

    ok, reason = mcp.login(server, notify=notify)
    if ok:
        term.type_out(t("configmenu.mcp_oauth_done"), delay=0.003)
    else:
        term.error(t("configmenu.mcp_oauth_failed", reason=reason))


def _firecrawl_menu(term, browser):
    from .sysop_config import firecrawl_key, set_firecrawl_key

    def rows():
        fc = load_section("firecrawl")
        return [
            ("1", "Firecrawl", _onoff(fc.get("enabled"))),
            ("2", t("configmenu.mode"), t("configmenu.mode_mcp") if fc.get("use_mcp") else t("configmenu.mode_sdk")),
            ("3", t("configmenu.api_key"), _mask(firecrawl_key(fc))),
            ("4", t("configmenu.host"), fc.get("base_url") or t("configmenu.host_cloud", cloud=FIRECRAWL_CLOUD)),
            ("5", t("configmenu.firecrawl_check_item"), t("configmenu.firecrawl_check_item_desc")),
        ]

    def store(fc):
        save_section("firecrawl", fc)
        browser.firecrawl = fc
        # Changed settings deserve a fresh attempt — even if Firecrawl was
        # switched off for the session after repeated failures.
        firecrawl_reset()

    def cycle(key, _direction):
        fc = load_section("firecrawl")
        if key == "1":
            fc["enabled"] = not fc.get("enabled")
        elif key == "2":
            fc["use_mcp"] = not fc.get("use_mcp")
        else:
            return False
        store(fc)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_firecrawl"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        fc = load_section("firecrawl")
        if choice == "3":
            set_firecrawl_key(fc, term.prompt(t("configmenu.prompt_firecrawl_key")).strip())
        elif choice == "4":
            fc["base_url"] = normalize_base_url(term.prompt(t("configmenu.prompt_host")))
        elif choice == "5":
            # MCP needs the direct Anthropic key — check exactly that one.
            from .sysop_config import config_key
            run_firecrawl_check(term, fc, config_key(load_section("ai"), "anthropic"))
            continue
        else:
            term.error(t("configmenu.invalid_choice"))
            continue
        store(fc)


def _width_label(width_cfg):
    """Label for the terminal width: unconfigured = 80, 0 = full screen."""
    if width_cfg is None:
        return t("configmenu.term_width_default")
    try:
        value = int(width_cfg)
    except (ValueError, TypeError):
        return t("configmenu.term_width_default")
    if value <= 0:
        return t("configmenu.term_width_full", cols=screen_width())
    return str(value) if value > 80 else t("configmenu.term_width_default")


def _display_menu(term, browser):
    def color_mode():
        if browser.color_auto:
            return "auto"
        if colors.multi_active():
            return "multi"
        return "green" if term.color == GREEN else "amber"

    def rows():
        width_cfg = load_section("ui").get("width")
        return [
            (None, t("configmenu.sect_page"), ""),
            ("1", t("configmenu.images"), t("configmenu.images_" + browser.images)),
            ("2", t("configmenu.image_width"), str(browser.img_width)),
            ("3", t("configmenu.header"), t("configmenu.header_" + browser.header)),
            (None, t("configmenu.sect_term"), ""),
            ("4", t("configmenu.color"), t("configmenu.color_" + color_mode())),
            ("5", t("configmenu.term_width"), _width_label(width_cfg)),
            ("6", t("configmenu.typing_effect"), _onoff(not term.fast)),
            ("7", t("configmenu.baud_sim"), f"{term.baud} BAUD" if term.baud else t("configmenu.baud_off")),
            ("8", t("configmenu.sound"), _onoff(term.sound) + "  " + t("configmenu.sound_desc")),
            ("9", t("configmenu.screensaver"), t("configmenu.screensaver_on", secs=browser.saver_idle)
                                                if browser.saver_idle else t("configmenu.off")),
            ("10", t("configmenu.language"), "Deutsch" if i18n.get_lang() == "de" else "English"),
            ("11", t("configmenu.item_reset"), t("configmenu.reset_display_desc")),
        ]

    def cycle(key, direction):
        if key == "1":
            browser.images = set_ui("images", _cycle(IMG_SETTINGS, browser.images, direction))
        elif key == "3":
            browser.header = set_ui("header", _cycle(HEADER_MODES, browser.header, direction))
        elif key == "4":
            mode = _cycle(COLOR_MODES, color_mode(), direction)
            browser.color_auto = mode == "auto"
            colors.set_multi(mode == "multi")
            if mode == "multi":
                term.color = colors.MULTI_TEXT
            elif mode != "auto":
                term.color = GREEN if mode == "green" else AMBER
            set_ui("color", mode)
        elif key == "6":
            term.fast = toggle_ui("fast", term.fast)
        elif key == "7":
            term.baud = set_ui("baud", _cycle(BAUD_RATES, term.baud, direction))
        elif key == "8":
            term.sound = toggle_ui("sound", term.sound)
        elif key == "10":
            i18n.set_lang(set_ui("lang", _cycle(i18n.LANGUAGES, i18n.get_lang(), direction)))
        else:
            return False
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_display"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        # Rows whose Enter does more than just toggle come first.
        if choice == "1" and cycle(choice, 1):
            term.type_out(t("configmenu.image_mode_hint"))
            continue
        if choice == "3":
            cycle(choice, 1)
            _after_header_change(term, browser)
            continue
        if cycle(choice, 1):
            continue
        if choice == "2":
            _ask_number(term, t("configmenu.prompt_image_width"),
                        lambda v: setattr(browser, "img_width", set_ui("img_width", max(10, v))))
        elif choice == "9":
            _ask_number(term, t("configmenu.prompt_screensaver"),
                        lambda v: setattr(browser, "saver_idle", set_ui("saver_idle", max(0, v))))
        elif choice == "5":
            # Empty input cancels; "0" switches to full screen (no cap).
            raw = term.prompt(t("configmenu.prompt_term_width")).strip()
            if raw:
                try:
                    value = int(raw)
                except ValueError:
                    term.error(t("configmenu.invalid_number"))
                else:
                    set_ui("width", 0 if value <= 0 else max(80, value))
                    invalidate_layout()
                    term.type_out(t("configmenu.term_width_applied", cols=screen_width()))
        elif choice == "11":
            if _confirm(term, "configmenu.reset_display_confirm"):
                _reset_display(term, browser)
                term.type_out(t("configmenu.reset_done"), delay=0.003)
        else:
            term.error(t("configmenu.invalid_choice"))


def _after_header_change(term, browser):
    """After switching the page header, force a refetch of the cached banner
    or logo of the current domain."""
    if not browser.page:
        return
    domain = urlparse(browser.page.url).netloc.removeprefix("www.")
    if not domain:
        return
    if browser.header == "logo":
        headers.forget_logo(domain)
    elif browser.header == "banner":
        if term.prompt(t("configmenu.page_header_reset")).lower() in ("j", "y"):
            headers.reset(domain)
            term.type_out(t("configmenu.page_header_redrawn"))


def _ask_number(term, prompt, apply):
    """Number prompt with a consistent error message."""
    try:
        apply(int(term.prompt(prompt) or 0))
    except ValueError:
        term.error(t("configmenu.invalid_number"))
