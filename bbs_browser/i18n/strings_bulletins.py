"""Texte des Bulletin-Boards (KI-Meldungen aus einer News-Quelle)."""

STRINGS = {
    "bulletins.prompt_system": {
        "de": (
            "Du bist der SysOp einer Mailbox von 1989 und schreibst das taegliche "
            "Bulletin-Board. Waehle aus den nummerierten Schlagzeilen die {count} "
            "wichtigsten aus und formuliere zu jeder EINE Zeile im knappen, leicht "
            "nostalgischen SysOp-Ton, hoechstens {chars} Zeichen. Keine Emojis, keine "
            "Anfuehrungszeichen, keine Einleitung. Antworte ausschliesslich mit einer "
            "Zeile pro Meldung im Format: <nummer>|<text>"
        ),
        "en": (
            "You are the SysOp of a 1989 bulletin board writing today's bulletins. "
            "Pick the {count} most relevant of the numbered headlines and write ONE "
            "line for each in a terse, faintly nostalgic SysOp tone, at most {chars} "
            "characters. No emojis, no quotes, no preamble. Answer with nothing but "
            "one line per bulletin in the format: <number>|<text>"
        ),
    },
    "bulletins.prompt_user": {
        "de": "Quelle: {source}\nSchlagzeilen:\n{headlines}\n\nSchreibe {count} Bulletins.",
        "en": "Source: {source}\nHeadlines:\n{headlines}\n\nWrite {count} bulletins.",
    },
    "bulletins.page_title": {"de": "BULLETINS", "en": "BULLETINS"},
    "bulletins.page_heading_multi": {"de": "BULLETIN-BOARD — Quellen: {source}", "en": "BULLETIN BOARD — sources: {source}"},
    "bulletins.source_mixed": {"de": "{first} +{rest} weitere", "en": "{first} +{rest} more"},
    "bulletins.age_min": {"de": "vor {minutes} min", "en": "{minutes} min ago"},
    "bulletins.age_hour": {"de": "vor {hours} h", "en": "{hours} h ago"},
    "bulletins.age_day": {"de": "vor {days} T", "en": "{days} d ago"},
    "bulletins.page_heading": {"de": "BULLETIN-BOARD — Quelle: {source}", "en": "BULLETIN BOARD — source: {source}"},
    "bulletins.page_empty": {
        "de": "Keine Meldungen. Quellen im Konfigmenue setzen: 'c' > Bulletins.",
        "en": "No bulletins yet. Set your sources in the config menu: 'c' > Bulletins.",
    },
    "bulletins.page_age_instant": {"de": "Stand: vor {hours} h — Auffrischung bei jeder Anwahl.", "en": "As of {hours} h ago — refreshed on every dial-up."},
    "bulletins.page_age": {"de": "Stand: vor {hours} h — Auffrischung alle {ttl} h.", "en": "As of {hours} h ago — refreshed every {ttl} h."},
    "bulletins.page_age_feed": {"de": "Stand: vor {minutes} min — Auffrischung alle {ttl} min.", "en": "As of {minutes} min ago — refreshed every {ttl} min."},
    "bulletins.menu_hint": {
        "de": "↑↓ waehlen · ENTER Artikel anwaehlen · ESC zurueck",
        "en": "↑↓ select · ENTER dial the article · ESC back",
    },
    "bulletins.no_key": {"de": "Ohne KI-Schluessel gibt es keine Bulletins.", "en": "No AI key, no bulletins."},
    "bulletins.no_url": {"de": "Keine News-Quelle gesetzt: 'c' > Bulletins.", "en": "No news source configured: 'c' > Bulletins."},
    "bulletins.fetching": {"de": "SYS 0x2B — Bulletins werden gesetzt ...", "en": "SYS 0x2B — setting bulletins ..."},
    "bulletins.refreshed": {"de": "{count} Bulletins gesetzt.", "en": "{count} bulletins posted."},
    "bulletins.refresh_failed": {"de": "ERR 41 — Quelle lieferte nichts.", "en": "ERR 41 — source returned nothing."},
    "bulletins.cleared": {"de": "Bulletins verworfen.", "en": "Bulletins discarded."},
}
