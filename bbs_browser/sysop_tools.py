"""Tool registries of the AI SysOp agent.

Free functions that build the provider-neutral tool lists: each entry has
name, description, a JSON schema (parameters) and the Python function.
Extracted from sysop.py so the SysOp class stays focused on the agent loop.
"""

import subprocess

from . import db
from .i18n import t
from .sysop_config import (MAX_PAGE_CHARS, MAX_SHELL_OUTPUT, firecrawl_key,
                           shell_config, shell_enabled)


def build_tool_registry(sysop):
    """Provider-neutral tool list: each entry has name, description, a
    JSON schema (parameters) and the Python function. Anthropic and OpenAI
    build their respective tool format from this (see _*_tool_defs)."""
    browser = sysop.browser

    def _no_params():
        return {"type": "object", "properties": {}}

    def _one(name, typ, desc):
        return {"type": "object", "properties": {name: {"type": typ, "description": desc}},
                "required": [name]}

    def seite_lesen():
        if not browser or not browser.page:
            return t("sysop.no_page_loaded")
        return sysop._page_text(browser.page)

    def links_auflisten():
        if not browser or not browser.page or not browser.page.links:
            return t("sysop.no_links_available")
        listing = "\n".join(
            f"[{i}] {label} -> {url}"
            for i, (url, label) in enumerate(browser.page.links, 1)
        )
        return listing[:MAX_PAGE_CHARS]

    def link_folgen(nummer):
        if not browser or not browser.page:
            return t("sysop.no_page_loaded")
        url = browser.page.link_url(int(nummer))
        if not url:
            return t("sysop.link_not_found", number=nummer, total=len(browser.page.links))
        browser.dial(url)
        return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)

    def seite_anwaehlen(url):
        if not browser:
            return t("sysop.error_browser_unavailable")
        browser.dial(url)
        if browser.page:
            return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
        return t("sysop.error_dial_failed")

    def suchen(begriff):
        if not browser:
            return t("sysop.error_browser_unavailable")
        browser.search(begriff)
        if browser.page:
            return t("sysop.search_results_loaded")
        return t("sysop.search_failed")

    def im_netz_lesen(url):
        from .fetch import fetch_page, normalize_url
        fc_cfg = browser.firecrawl if browser else {}
        page, err = fetch_page(normalize_url(url), fc_cfg)
        if err:
            return t("sysop.error_no_carrier", error=err)
        snapshot = sysop._page_snapshot(page)
        # Firecrawl was on but failed (silent HTTP fallback): the
        # reason belongs in the tool result, otherwise the AI is left guessing.
        fc_error = getattr(page, "firecrawl_error", "")
        if fc_error:
            snapshot = t("sysop.firecrawl_note", error=fc_error) + "\n\n" + snapshot
        return snapshot

    def im_netz_suchen(begriff):
        from urllib.parse import quote_plus
        from .firecrawl import firecrawl_search
        from .fetch import fetch_page, normalize_base_url
        from .page import page_text
        fc_cfg = browser.firecrawl if browser else {}
        fc_key = firecrawl_key(fc_cfg)
        fc_base = normalize_base_url(fc_cfg.get("base_url"))
        fc_err = None
        # Firecrawl configured? Then use the real search API — the
        # DDG HTML now mostly blocks automated requests.
        if fc_cfg.get("enabled") and (fc_key or fc_base):
            results, fc_err = firecrawl_search(begriff, fc_key, fc_base)
            if results:
                listing = "\n".join(
                    f"[{i}] {title} -> {url}" + (f"\n    {desc}" if desc else "")
                    for i, (url, title, desc) in enumerate(results, 1)
                )
                return listing[:MAX_PAGE_CHARS]
        page, err = fetch_page(
            "https://html.duckduckgo.com/html/?q=" + quote_plus(begriff), fc_cfg
        )
        if page and page.links:
            listing = "\n".join(
                f"[{i}] {label} -> {url}"
                for i, (url, label) in enumerate(page.links, 1)
            )
            return listing[:MAX_PAGE_CHARS]
        # Nothing found: collect all reasons so the AI can tell
        # the caller WHY the search came back empty.
        reasons = [r for r in (
            fc_err, err, getattr(page, "firecrawl_error", "") if page else "",
        ) if r]
        if page:
            # DDG responded, but without result links — usually the
            # bot block; its message text explains the situation to the AI.
            excerpt = page_text(page)[:300].strip()
            if excerpt:
                reasons.append(t("sysop.search_page_said", excerpt=excerpt))
        if reasons:
            return t("sysop.search_failed") + " " + " | ".join(reasons)
        return t("sysop.no_search_results")

    def funktionen_auflisten():
        from . import manual
        return "\n".join(
            f"{key} | {syntax} | {category} | {kurz}"
            for key, syntax, category, kurz, _ in manual.ALL
        )

    def funktion_erklaeren(name):
        from . import manual
        text = manual.explain(name)
        if text:
            return text
        keys = ", ".join(entry[0] for entry in manual.ALL)
        return t("sysop_tools.function_not_found", name=name, keys=keys)  # internal error for the AI

    def chat_umbenennen(titel):
        from .sysop import CHAT_TITLE_MAX
        titel = (titel or "").strip()[:CHAT_TITLE_MAX]
        db.chat_set_title(sysop.chat_channel, titel)
        if titel:
            return t("sysop.chat_renamed", title=titel)
        return t("sysop.chat_rename_cleared")

    def system_befehl(befehl):
        mode, timeout = shell_config()
        if mode == "off":
            return t("sysop.shell_disabled")
        befehl = (befehl or "").strip()
        if not befehl:
            return t("sysop.shell_empty")
        if mode == "confirm":
            # The caller sees the command in plain text and approves it —
            # without an explicit yes, nothing happens.
            sysop.term.type_out(t("sysop.shell_ask", command=befehl), delay=0.002)
            if not sysop.term.confirm(t("sysop.shell_confirm_prompt")):
                return t("sysop.shell_denied")
        sysop.term.type_out(t("sysop.shell_running", command=befehl), delay=0.001)
        try:
            proc = subprocess.run(
                befehl, shell=True, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return t("sysop.shell_timeout", seconds=timeout)
        except Exception as e:
            return t("sysop.shell_error", error=str(e))
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part.strip())
        output = output.strip() or t("sysop.shell_no_output")
        return t("sysop.shell_result", code=proc.returncode,
                 output=output[:MAX_SHELL_OUTPUT])

    def firecrawl_scrape(url):
        fc_cfg = browser.firecrawl if browser else {}
        md = sysop.scrape_markdown(url, fc_cfg)
        return md[:MAX_PAGE_CHARS] if md else t("sysop_tools.scrape_failed")

    # -- App control: navigation, bookmarks, non-critical settings --

    def zurueck_blaettern():
        if not browser:
            return t("sysop.error_browser_unavailable")
        browser.back()
        if browser.page:
            return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
        return t("sysop.no_page_loaded")

    def verlauf_anzeigen():
        from .nostalgia import recent_entries
        if not browser or not browser.history:
            return t("sysop_tools.history_empty")
        return "\n".join(
            f"[{i}] {e.get('title') or ''} -> {e.get('url')}"
            for i, e in enumerate(recent_entries(browser.history, 20), 1))

    def lesezeichen_auflisten():
        if not browser or not browser.bookmarks:
            return t("sysop_tools.no_bookmarks")
        return "\n".join(
            f"[{i}] {b.get('title') or ''} -> {b.get('url')}"
            for i, b in enumerate(browser.bookmarks, 1))

    def lesezeichen_setzen():
        if not browser or not browser.page:
            return t("sysop.no_page_loaded")
        browser.add_bookmark()
        return t("sysop_tools.bookmark_set", title=browser.page.title, url=browser.page.url)

    def lesezeichen_anwaehlen(nummer):
        if not browser:
            return t("sysop.error_browser_unavailable")
        browser.dial_bookmark(int(nummer))
        if browser.page:
            return t("sysop.page_loaded", title=browser.page.title, url=browser.page.url)
        return t("sysop.no_page_loaded")

    # Non-critical settings: everything from the display menu. API keys,
    # system access and MCP servers are deliberately left out — only the
    # caller can change those in the config menu.
    def _wahr(wert):
        return str(wert).strip().lower() in ("1", "an", "on", "true", "ja", "yes", "ein")

    def _settings_map():
        from . import i18n
        from .constants import (AMBER, GREEN, HEADER_MODES, IMG_SETTINGS,
                                invalidate_layout)
        from .state import set_ui

        def farbe(wert):
            from . import colors

            mode = str(wert).strip().lower()
            if mode not in ("green", "amber", "auto", "multi"):
                return t("sysop_tools.color_allowed")
            browser.color_auto = mode == "auto"
            colors.set_multi(mode == "multi")
            if mode == "multi":
                sysop.term.color = colors.MULTI_TEXT
            elif mode != "auto":
                sysop.term.color = GREEN if mode == "green" else AMBER
            set_ui("color", mode)
            return None

        def sprache(wert):
            lang = str(wert).strip().lower()
            if lang not in i18n.LANGUAGES:
                return t("sysop_tools.lang_allowed", list=", ".join(i18n.LANGUAGES))
            i18n.set_lang(set_ui("lang", lang))
            return None

        def breite(wert):
            value = int(wert)
            set_ui("width", 0 if value <= 0 else max(80, value))
            invalidate_layout()
            return None

        def bilder(wert):
            mode = str(wert).strip().lower()
            mode = {"aus": "off", "an": "blocks", "bloecke": "blocks",
                    "halbbloecke": "blocks"}.get(mode, mode)
            if mode not in IMG_SETTINGS:
                return t("sysop_tools.images_allowed")
            browser.images = set_ui("images", mode)
            return None

        def seitenkopf(wert):
            mode = str(wert).strip().lower()
            mode = {"aus": "off", "an": "logo"}.get(mode, mode)
            if mode not in HEADER_MODES:
                return t("sysop_tools.header_allowed")
            browser.header = set_ui("header", mode)
            return None

        def _bool_setter(ui_key, apply):
            def setter(wert):
                value = _wahr(wert)
                set_ui(ui_key, apply(value) if apply else value)
                return None
            return setter

        return {
            "bilder": (t("sysop_tools.setting_bilder"), bilder),
            "bildbreite": (t("sysop_tools.setting_bildbreite"),
                           lambda w: setattr(browser, "img_width", set_ui("img_width", max(10, int(w)))) and None),
            "tipp_effekt": (t("sysop_tools.setting_tipp_effekt"),
                            _bool_setter("fast", lambda v: _set_fast(not v))),
            "farbe": (t("sysop_tools.setting_farbe"), farbe),
            "baud": (t("sysop_tools.setting_baud"),
                     lambda w: _set_baud(set_ui("baud", max(0, int(w))))),
            "sound": (t("sysop_tools.setting_sound"),
                      _bool_setter("sound", lambda v: _set_sound(v))),
            "bildschirmschoner": (t("sysop_tools.setting_bildschirmschoner"),
                                  lambda w: setattr(browser, "saver_idle", set_ui("saver_idle", max(0, int(w)))) and None),
            "sprache": (t("sysop_tools.setting_sprache"), sprache),
            "breite": (t("sysop_tools.setting_breite"), breite),
            "seitenkopf": (t("sysop_tools.setting_seitenkopf"), seitenkopf),
        }

    def _set_fast(value):
        sysop.term.fast = value
        return value

    def _set_baud(value):
        sysop.term.baud = value
        return None

    def _set_sound(value):
        sysop.term.sound = value
        return value

    def einstellungen_auflisten():
        if not browser:
            return t("sysop.error_browser_unavailable")
        return "\n".join(f"{name} — {desc}"
                         for name, (desc, _) in sorted(_settings_map().items()))

    def einstellung_aendern(name, wert):
        if not browser:
            return t("sysop.error_browser_unavailable")
        settings = _settings_map()
        entry = settings.get(str(name).strip().lower())
        if not entry:
            return t("sysop_tools.setting_unknown", list=", ".join(sorted(settings)))
        desc, setter = entry
        try:
            problem = setter(wert)
        except (TypeError, ValueError):
            return t("sysop_tools.setting_invalid_value", name=name, desc=desc)
        if problem:
            return problem
        return t("sysop_tools.setting_changed", name=name, value=wert)

    tools = [
        {"name": "seite_lesen", "func": seite_lesen, "parameters": _no_params(),
         "description": t("sysop_tools.seite_lesen_desc")},
        {"name": "links_auflisten", "func": links_auflisten, "parameters": _no_params(),
         "description": t("sysop_tools.links_auflisten_desc")},
        {"name": "link_folgen", "func": link_folgen,
         "parameters": _one("nummer", "integer", t("sysop_tools.link_folgen_param_nummer")),
         "description": t("sysop_tools.link_folgen_desc")},
        {"name": "seite_anwaehlen", "func": seite_anwaehlen,
         "parameters": _one("url", "string", t("sysop_tools.seite_anwaehlen_param_url")),
         "description": t("sysop_tools.seite_anwaehlen_desc")},
        {"name": "suchen", "func": suchen,
         "parameters": _one("begriff", "string", t("sysop_tools.suchen_param_begriff")),
         "description": t("sysop_tools.suchen_desc")},
        {"name": "im_netz_lesen", "func": im_netz_lesen,
         "parameters": _one("url", "string", t("sysop_tools.im_netz_lesen_param_url")),
         "description": t("sysop_tools.im_netz_lesen_desc")},
        {"name": "im_netz_suchen", "func": im_netz_suchen,
         "parameters": _one("begriff", "string", t("sysop_tools.im_netz_suchen_param_begriff")),
         "description": t("sysop_tools.im_netz_suchen_desc")},
        {"name": "funktionen_auflisten", "func": funktionen_auflisten, "parameters": _no_params(),
         "description": t("sysop_tools.funktionen_auflisten_desc")},
        {"name": "funktion_erklaeren", "func": funktion_erklaeren,
         "parameters": _one("name", "string", t("sysop_tools.funktion_erklaeren_param_name")),
         "description": t("sysop_tools.funktion_erklaeren_desc")},
        {"name": "chat_umbenennen", "func": chat_umbenennen,
         "parameters": _one("titel", "string", t("sysop_tools.chat_umbenennen_param_titel")),
         "description": t("sysop_tools.chat_umbenennen_desc")},
        {"name": "firecrawl_scrape", "func": firecrawl_scrape,
         "parameters": _one("url", "string", t("sysop_tools.firecrawl_scrape_param_url")),
         "description": t("sysop_tools.firecrawl_scrape_desc")},
        {"name": "zurueck_blaettern", "func": zurueck_blaettern, "parameters": _no_params(),
         "description": t("sysop_tools.zurueck_blaettern_desc")},
        {"name": "verlauf_anzeigen", "func": verlauf_anzeigen, "parameters": _no_params(),
         "description": t("sysop_tools.verlauf_anzeigen_desc")},
        {"name": "lesezeichen_auflisten", "func": lesezeichen_auflisten, "parameters": _no_params(),
         "description": t("sysop_tools.lesezeichen_auflisten_desc")},
        {"name": "lesezeichen_setzen", "func": lesezeichen_setzen, "parameters": _no_params(),
         "description": t("sysop_tools.lesezeichen_setzen_desc")},
        {"name": "lesezeichen_anwaehlen", "func": lesezeichen_anwaehlen,
         "parameters": _one("nummer", "integer", t("sysop_tools.lesezeichen_anwaehlen_param_nummer")),
         "description": t("sysop_tools.lesezeichen_anwaehlen_desc")},
        {"name": "einstellungen_auflisten", "func": einstellungen_auflisten, "parameters": _no_params(),
         "description": t("sysop_tools.einstellungen_auflisten_desc")},
        {"name": "einstellung_aendern", "func": einstellung_aendern,
         "parameters": {"type": "object", "properties": {
             "name": {"type": "string", "description": t("sysop_tools.einstellung_aendern_param_name")},
             "wert": {"type": "string", "description": t("sysop_tools.einstellung_aendern_param_wert")},
         }, "required": ["name", "wert"]},
         "description": t("sysop_tools.einstellung_aendern_desc")},
    ]
    # Tools of the registered MCP servers: our own MCP client makes
    # them available to every provider, not just direct Anthropic.
    try:
        from . import mcp
        tools.extend(mcp.registry_tools())
    except Exception:
        pass    # a broken MCP server must not block the chat
    # System access is only offered to the model if the caller has
    # enabled it — otherwise the agent doesn't even know the tool exists.
    if shell_enabled():
        tools.append({
            "name": "system_befehl", "func": system_befehl,
            "parameters": _one("befehl", "string",
                               t("sysop_tools.system_befehl_param_befehl")),
            "description": t("sysop_tools.system_befehl_desc"),
        })
    return tools


def build_templater_registry(box):
    """The learning loop's tools in the agent format (see
    build_tool_registry) — named like the trade they imitate: a type spec, a
    blueprint, a proof run. Deliberately only these three: the setter is
    meant to examine the site, not remote-control the browser."""
    def _sel(required, desc):
        schema = {"type": "object",
                  "properties": {"selektor": {"type": "string", "description": desc}}}
        if required:
            schema["required"] = ["selektor"]
        return schema

    return [
        {
            "name": "satzprobe",
            "description": t("sysop_tools.satzprobe_desc"),
            "parameters": _sel(True, t("sysop_tools.satzprobe_param_selektor")),
            "func": lambda selektor: box.probe(selektor),
        },
        {
            "name": "bauplan",
            "description": t("sysop_tools.bauplan_desc"),
            "parameters": _sel(False, t("sysop_tools.bauplan_param_selektor")),
            "func": lambda selektor="": box.outline(selektor),
        },
        {
            "name": "andruck",
            "description": t("sysop_tools.andruck_desc"),
            "parameters": {
                "type": "object",
                "properties": {"vorlage": {
                    "type": "string",
                    "description": t("sysop_tools.andruck_param_vorlage"),
                }},
                "required": ["vorlage"],
            },
            "func": lambda vorlage: box.preview(vorlage),
        },
    ]
