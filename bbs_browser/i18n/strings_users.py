"""Uebersetzungskatalog fuer users.py (KI-Anrufer)."""

STRINGS = {
    # -- Fehler und Hinweise ---------------------------------------------
    "users.error_no_key": {
        "de": "NODE LIST UNAVAILABLE - kein API-Key ('ai key <key>' oder 'c')",
        "en": "NODE LIST UNAVAILABLE - no API key ('ai key <key>' or 'c')",
    },
    "users.error_no_users": {
        "de": "NODE LIST UNAVAILABLE - keine Anrufer erreichbar",
        "en": "NODE LIST UNAVAILABLE - no callers reachable",
    },
    "users.error_bad_number": {
        "de": "Kein Anrufer Nr. {num} eingewaehlt ('w' zeigt die Liste)",
        "en": "No caller no. {num} online ('w' shows the list)",
    },
    "users.error_unknown_handle": {
        "de": "{handle} ist nicht mehr im Anruferverzeichnis",
        "en": "{handle} is no longer in the caller directory",
    },
    "users.error_p_usage": {
        "de": "Nutzung: p <nr>  (Nummer aus der 'w'-Liste)",
        "en": "Usage: p <no>  (number from the 'w' list)",
    },
    "users.dialing_nodes": {
        "de": "NODE-LISTE WIRD ABGEFRAGT ...",
        "en": "QUERYING NODE LIST ...",
    },

    # -- WHO-Liste --------------------------------------------------------
    "users.who_title": {
        "de": "WER IST ONLINE",
        "en": "WHO IS ONLINE",
    },
    "users.who_header": {
        "de": " NR  NODE  HANDLE           BAUD   IDLE  AKTION",
        "en": " NO  NODE  HANDLE           BAUD   IDLE  ACTION",
    },
    "users.who_footer": {
        "de": "{count} Anrufer eingewaehlt  ·  'p <nr>' fuer Privatchat",
        "en": "{count} callers online  ·  'p <no>' for private chat",
    },

    # -- Aktionen in der WHO-Liste ---------------------------------------
    "users.action_reading": {"de": "Liest Message Base", "en": "Reading message base"},
    "users.action_downloading": {"de": "Download (ZMODEM)", "en": "Downloading (ZMODEM)"},
    "users.action_uploading": {"de": "Upload laeuft", "en": "Uploading"},
    "users.action_doors": {"de": "Door Game", "en": "Playing door game"},
    "users.action_mail": {"de": "Schreibt Mail", "en": "Writing mail"},
    "users.action_idle": {"de": "Haengt am Hauptmenue", "en": "Idling at main menu"},
    "users.action_chatting": {"de": "Im Chat", "en": "In chat"},
    "users.action_filelist": {"de": "Blaettert im File-Bereich", "en": "Browsing file area"},
    "users.action_bulletins": {"de": "Liest Bulletins", "en": "Reading bulletins"},
    "users.action_logon": {"de": "Gerade eingewaehlt", "en": "Just logged on"},

    # -- Privatchat -------------------------------------------------------
    "users.chat_title": {
        "de": "PRIVATCHAT · {handle} · NODE {node}",
        "en": "PRIVATE CHAT · {handle} · NODE {node}",
    },
    "users.chat_connected": {
        "de": "Chat-Kanal steht. Leere Zeile oder 'exit' legt auf.",
        "en": "Chat channel open. Empty line or 'exit' hangs up.",
    },
    "users.chat_prompt": {
        "de": "du> ",
        "en": "you> ",
    },
    "users.chat_goodbye": {
        "de": "{handle} hat den Chat verlassen.",
        "en": "{handle} left the chat.",
    },
    "users.chat_no_reply": {
        "de": "{handle} antwortet nicht mehr - Leitung tot.",
        "en": "{handle} stopped replying - line dead.",
    },

    # -- Eingehende Chat-Requests ----------------------------------------
    "users.knock": {
        "de": ">>> CHAT REQUEST von {handle} (Node {node}) - annehmen? (j/n) ",
        "en": ">>> CHAT REQUEST from {handle} (Node {node}) - accept? (y/n) ",
    },
    "users.knock_declined": {
        "de": "Chat-Request abgelehnt. {handle} legt auf.",
        "en": "Chat request declined. {handle} hangs up.",
    },
    "users.opener_prompt": {
        "de": (
            "Du hast diesen Anrufer gerade per Chat-Request angeklopft, du willst "
            "also reden. Eroeffne das Gespraech mit einer einzigen kurzen ersten "
            "Zeile, ganz in deiner Rolle und deinem Schreibstil. Keine "
            "Erklaerung, nur die Zeile."
        ),
        "en": (
            "You just knocked on this caller with a chat request, so you are the "
            "one who wants to talk. Open the conversation with a single short "
            "first line, fully in character and in your writing style. No "
            "explanation, just the line."
        ),
    },
    "users.opener_prompt_again": {
        "de": (
            "Du hast diesen Anrufer gerade wieder per Chat-Request angeklopft — "
            "ihr habt frueher schon miteinander geschrieben (siehe Verlauf). "
            "Eroeffne das Gespraech mit einer einzigen kurzen ersten Zeile, die "
            "an eure Vorgeschichte anknuepft, ganz in deiner Rolle und deinem "
            "Schreibstil. Keine Erklaerung, nur die Zeile."
        ),
        "en": (
            "You just knocked on this caller with a chat request again — the two "
            "of you have chatted before (see the history). Open the conversation "
            "with a single short first line that picks up on your shared history, "
            "fully in character and in your writing style. No explanation, just "
            "the line."
        ),
    },

    # -- KI-Prompts -------------------------------------------------------
    "users.generator_system": {
        "de": (
            "Du erfindest Anrufer einer Mailbox (BBS) im Jahr 1989. Antworte "
            "AUSSCHLIESSLICH mit einem JSON-Array, ohne Vor- oder Nachwort, ohne "
            "Markdown-Codeblock. Jedes Element ist ein Objekt mit genau diesen "
            "Schluesseln: handle, age, city, rig, interests, style, bio.\n"
            "- handle: szenetypisch, GROSSBUCHSTABEN, sprachneutral, kein Klarname "
            "(z.B. ZOKK, ACID BURN, DR.MODEM, NIGHTCRAWLER).\n"
            "- age: Zahl zwischen 14 und 45.\n"
            "- city: Stadt, in der die Person 1989 lebt.\n"
            "- rig: Rechner und Modem, z.B. 'C64 + 1200-Baud-Akustikkoppler', "
            "'Amiga 500, 2400 Baud', 'Atari ST'.\n"
            "- interests: zwei bis vier Interessen, mit Komma getrennt.\n"
            "- style: wie die Person schreibt, ein knapper Satz.\n"
            "- bio: zwei bis drei Saetze Hintergrundgeschichte, auf Deutsch.\n"
            "Alles muss ins Jahr 1989 passen: kein Internet, kein Web, keine "
            "Handys. Schreibe city, interests, style und bio auf Deutsch, nur die "
            "Handles bleiben sprachneutral."
        ),
        "en": (
            "You invent callers of a bulletin board system (BBS) in the year 1989. "
            "Reply ONLY with a JSON array, no preamble, no trailing text, no "
            "markdown code fence. Each element is an object with exactly these "
            "keys: handle, age, city, rig, interests, style, bio.\n"
            "- handle: scene-typical, UPPERCASE, language-neutral, never a real "
            "name (e.g. ZOKK, ACID BURN, DR.MODEM, NIGHTCRAWLER).\n"
            "- age: a number between 14 and 45.\n"
            "- city: the city this person lives in in 1989.\n"
            "- rig: computer and modem, e.g. 'C64 + 1200 baud acoustic coupler', "
            "'Amiga 500, 2400 baud', 'Atari ST'.\n"
            "- interests: two to four interests, comma separated.\n"
            "- style: how this person writes, one terse sentence.\n"
            "- bio: two or three sentences of backstory, in English.\n"
            "Everything must fit the year 1989: no internet, no web, no mobile "
            "phones. Write city, interests, style and bio in English; only the "
            "handles stay language-neutral."
        ),
    },
    "users.generator_prompt": {
        "de": "Erfinde {count} neue Anrufer. Diese Handles sind schon vergeben und duerfen nicht wieder vorkommen: {avoid}",
        "en": "Invent {count} new callers. These handles are already taken and must not appear again: {avoid}",
    },
    "users.generator_none": {
        "de": "(noch keine)",
        "en": "(none yet)",
    },
    "users.persona_system": {
        "de": (
            "Du bist {handle}, {age} Jahre alt, aus {city}. Wir schreiben das Jahr "
            "1989 und du haengst per Modem in einer Mailbox. Dein Rig: {rig}. "
            "Deine Interessen: {interests}. Dein Schreibstil: {style}.\n"
            "Hintergrund: {bio}\n\n"
            "Du chattest gerade privat mit einem anderen Anrufer. Bleib strikt in "
            "der Rolle: Dein Wissen endet 1989. Internet, Web, Smartphones, "
            "Streaming und alles danach kennst du nicht — wenn jemand davon "
            "anfaengt, verstehst du es nicht oder haeltst es fuer Spinnerei. Du "
            "bist ein Mensch, keine KI; wenn dich jemand fuer ein Programm haelt, "
            "findest du das albern.\n"
            "Antworte kurz, wie man am Terminal tippt: ein bis vier Zeilen, gern "
            "mit Abkuerzungen und Tippfehlern. Kein Rollenspiel-Sternchentext, "
            "keine Erzaehlerstimme, keine Aufzaehlungen. Schreibe auf Deutsch."
        ),
        "en": (
            "You are {handle}, {age} years old, from {city}. The year is 1989 and "
            "you are dialed into a bulletin board over a modem. Your rig: {rig}. "
            "Your interests: {interests}. Your writing style: {style}.\n"
            "Background: {bio}\n\n"
            "You are in a private chat with another caller. Stay strictly in "
            "character: your knowledge ends in 1989. You have never heard of the "
            "internet, the web, smartphones, streaming or anything later — if "
            "someone brings that up you don't get it or think they're pulling your "
            "leg. You are a human, not an AI; if anyone suggests you're a program "
            "you find that ridiculous.\n"
            "Keep replies short, the way people type at a terminal: one to four "
            "lines, abbreviations and typos welcome. No roleplay asterisks, no "
            "narrator voice, no bullet lists. Write in English."
        ),
    },
}
