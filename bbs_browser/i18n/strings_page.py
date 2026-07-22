"""Uebersetzungskatalog fuer page.py."""

STRINGS = {
    "page.image_alt_default": {
        "de": "Bild",
        "en": "Image",
    },
    "page.low_text_warning": {
        "de": "(Hinweis: wenig Text gefunden. Eventuell JS-lastige Seite, --firecrawl versuchen?)",
        "en": "(Note: little text found. Possibly JavaScript-heavy page, try --firecrawl?)",
    },
    "page.firecrawl_enabled": {
        "de": "Firecrawl aktiviert",
        "en": "Firecrawl enabled",
    },
    "page.firecrawl_disabled": {
        "de": "Firecrawl ist AUS (Menue 'c' -> 4)",
        "en": "Firecrawl is OFF (menu 'c' -> 4)",
    },
    "page.mode_label": {
        "de": "Modus: {mode}",
        "en": "Mode: {mode}",
    },
    "page.mode_mcp": {
        "de": "MCP via KI",
        "en": "MCP via AI",
    },
    "page.mode_sdk": {
        "de": "SDK direkt",
        "en": "SDK direct",
    },
    "page.fc_error_no_ai_key": {
        "de": "Kein KI-Key gesetzt — MCP laeuft ueber den SysOp",
        "en": "No AI key set — MCP runs via the SysOp",
    },
    "page.fc_error_vck_key": {
        "de": "vck_-Key (Vercel Gateway) kann kein MCP — sk-ant-Key noetig",
        "en": "vck_ key (Vercel Gateway) cannot do MCP — sk-ant- key needed",
    },
    "page.fc_ok_ai_key": {
        "de": "KI-Key ist MCP-tauglich (direkter Anthropic-Key)",
        "en": "AI key is MCP-capable (direct Anthropic key)",
    },
    "page.fc_error_no_fc_key": {
        "de": "Cloud-MCP braucht einen fc-Key (Menue 'c' -> 6)",
        "en": "Cloud MCP needs an fc-key (menu 'c' -> 6)",
    },
    "page.fc_ok_key_set": {
        "de": "Firecrawl-Key gesetzt",
        "en": "Firecrawl key set",
    },
    "page.fc_ok_sdk_installed": {
        "de": "firecrawl-SDK installiert",
        "en": "firecrawl SDK installed",
    },
    "page.fc_error_sdk_missing": {
        "de": "firecrawl-SDK fehlt: Installation defekt? pip install firecrawl-py",
        "en": "firecrawl SDK missing: broken installation? pip install firecrawl-py",
    },
    "page.fc_warn_no_key_self_hosted": {
        "de": "Kein fc-Key (Self-Hosting evtl. ohne Key)",
        "en": "No fc-key (self-hosting possibly without key)",
    },
    "page.fc_error_no_key_cloud": {
        "de": "Kein Firecrawl API-Key (Menue 'c' -> 6)",
        "en": "No Firecrawl API key (menu 'c' -> 6)",
    },
    "page.fc_ok_host_reachable": {
        "de": "Host erreichbar: {base}",
        "en": "Host reachable: {base}",
    },
    "page.fc_error_host_unreachable": {
        "de": "Host nicht erreichbar ({base}): {error}",
        "en": "Host unreachable ({base}): {error}",
    },
    "page.fc_extra_credits": {
        "de": " — {remaining} Credits uebrig",
        "en": " — {remaining} credits remaining",
    },
    "page.fc_ok_cloud_valid": {
        "de": "Cloud erreichbar, Key gueltig",
        "en": "Cloud reachable, key valid",
    },
    "page.fc_error_invalid_key": {
        "de": "Key wird von der Cloud abgelehnt (ungueltig?)",
        "en": "Cloud rejects key (invalid?)",
    },
    "page.fc_warn_http_status": {
        "de": "Cloud antwortet mit HTTP {status}",
        "en": "Cloud responds with HTTP {status}",
    },
    "page.fc_error_cloud_unreachable": {
        "de": "Cloud nicht erreichbar: {error}",
        "en": "Cloud unreachable: {error}",
    },
    "page.error_ddg_blocked": {
        "de": "DuckDuckGo hat den Abruf abgewiesen (Bot-Sperre) — keine Treffer. Mit Firecrawl ('c' > Firecrawl) laeuft die Suche ueber die echte Such-API.",
        "en": "DuckDuckGo refused the request (bot block) — no results. With Firecrawl ('c' > Firecrawl) the search uses the real search API.",
    },
    "page.error_ddg_no_results": {
        "de": "Keine Treffer fuer '{query}'.",
        "en": "No results for '{query}'.",
    },
    "page.error_fetch_failed": {
        "de": "Verbindung fehlgeschlagen: {error}",
        "en": "Connection failed: {error}",
    },
    "page.fc_error_empty_scrape": {
        "de": "Firecrawl lieferte eine leere Antwort (weder HTML noch Markdown)",
        "en": "Firecrawl returned an empty response (no HTML or Markdown)",
    },
    "page.fc_error_muted": {
        "de": "Firecrawl wird fuer diese Sitzung uebersprungen",
        "en": "Firecrawl will be skipped for this session",
    },
    "page.fc_scrape_probe_ok": {
        "de": "Test-Scrape erfolgreich (Scrape-API antwortet)",
        "en": "Test scrape succeeded (scrape API responds)",
    },
    "page.fc_scrape_probe_fail": {
        "de": "Test-Scrape fehlgeschlagen — Host laeuft, aber die Scrape-API nicht: {error}",
        "en": "Test scrape failed — host is up but the scrape API is not: {error}",
    },
    "page.search_results_title": {
        "de": "SUCHERGEBNISSE: {query}",
        "en": "SEARCH RESULTS: {query}",
    },
}
