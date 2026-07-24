"""Uebersetzungskatalog fuer sysop.py."""

STRINGS = {
    # Configuration and API errors
    "sysop.error_offline_no_api_key": {
        "de": "SYSOP OFFLINE - kein API-Key ('ai key <key>' oder 'c')",
        "en": "SYSOP OFFLINE - no API key ('ai key <key>' or 'c')",
    },
    "sysop.error_offline_missing_anthropic": {
        "de": "SYSOP OFFLINE - 'pip install anthropic' fehlt (oder: pip install '.[ai]')",
        "en": "SYSOP OFFLINE - 'pip install anthropic' missing (or: pip install '.[ai]')",
    },
    "sysop.error_offline_missing_openai": {
        "de": "SYSOP OFFLINE - 'pip install openai' fehlt (oder: pip install '.[ai]')",
        "en": "SYSOP OFFLINE - 'pip install openai' missing (or: pip install '.[ai]')",
    },
    "sysop.api_key_saved_for": {
        "de": "API-KEY GESPEICHERT fuer {provider} (~/.bbs_browser.db)",
        "en": "API KEY SAVED for {provider} (~/.bbs_browser.db)",
    },
    "sysop.model_set": {
        "de": "MODELL: {model}",
        "en": "MODEL: {model}",
    },
    "sysop.provider_set": {
        "de": "ANBIETER: {provider}",
        "en": "PROVIDER: {provider}",
    },
    "sysop.provider_unknown": {
        "de": "Unbekannter Anbieter '{name}'. Waehle: {list}",
        "en": "Unknown provider '{name}'. Choose: {list}",
    },
    "sysop.provider_no_key": {
        "de": "  Hinweis: fuer {provider} ist noch kein Key hinterlegt ('ai key <key>').",
        "en": "  Note: no key stored for {provider} yet ('ai key <key>').",
    },

    # Status display
    "sysop.status_title": {
        "de": "SYSOP STATUS",
        "en": "SYSOP STATUS",
    },
    "sysop.status_route_vercel": {
        "de": "Vercel AI Gateway",
        "en": "Vercel AI Gateway",
    },
    "sysop.status_route_anthropic": {
        "de": "Anthropic direkt",
        "en": "Anthropic direct",
    },
    "sysop.status_route_openai": {
        "de": "OpenAI",
        "en": "OpenAI",
    },
    "sysop.status_providers": {
        "de": "  Anbieter: {providers}  (* = aktiv, [x] = Key hinterlegt)",
        "en": "  Providers: {providers}  (* = active, [x] = key set)",
    },
    "sysop.status_online": {
        "de": "  ONLINE via {route}",
        "en": "  ONLINE via {route}",
    },
    "sysop.status_model": {
        "de": "  Modell: {model}",
        "en": "  Model: {model}",
    },
    "sysop.status_offline": {
        "de": "  OFFLINE - 'ai key <key>' zum Hinterlegen",
        "en": "  OFFLINE - 'ai key <key>' to configure",
    },
    "sysop.status_commands": {
        "de": "  Befehle: sum=Zusammenfassung  ask <frage>  go <beschreibung>  chat"
              "  ·  'ai provider <name>' wechselt den Anbieter",
        "en": "  Commands: sum=summary  ask <question>  go <description>  chat"
              "  ·  'ai provider <name>' switches provider",
    },

    # Tool responses
    "sysop.no_page_loaded": {
        "de": "Es ist keine Seite geladen.",
        "en": "No page is loaded.",
    },
    "sysop.no_links_available": {
        "de": "Keine Links vorhanden.",
        "en": "No links available.",
    },
    "sysop.link_not_found": {
        "de": "Link Nr. {number} existiert nicht (1-{total}).",
        "en": "Link #{number} not found (1-{total}).",
    },
    "sysop.page_loaded": {
        "de": "Geladen: {title} ({url})",
        "en": "Loaded: {title} ({url})",
    },
    "sysop.error_browser_unavailable": {
        "de": "Browser nicht verfuegbar.",
        "en": "Browser not available.",
    },
    "sysop.error_dial_failed": {
        "de": "Anwahl fehlgeschlagen (NO CARRIER).",
        "en": "Dial failed (NO CARRIER).",
    },
    "sysop.search_results_loaded": {
        "de": "Suchergebnisse geladen. Nutze seite_lesen oder links_auflisten.",
        "en": "Search results loaded. Use seite_lesen or links_auflisten.",
    },
    "sysop.search_failed": {
        "de": "Suche fehlgeschlagen.",
        "en": "Search failed.",
    },
    "sysop.error_no_carrier": {
        "de": "NO CARRIER - {error}",
        "en": "NO CARRIER - {error}",
    },
    "sysop.no_search_results": {
        "de": "Keine Treffer.",
        "en": "No results.",
    },
    "sysop.search_page_said": {
        "de": "Antwort der Suchseite: {excerpt}",
        "en": "The search page replied: {excerpt}",
    },
    # System access (shell)
    "sysop.shell_disabled": {
        "de": "Systemzugriff ist abgeschaltet. Der Anrufer kann ihn im Menue 'c' unter 'Systemzugriff' freigeben.",
        "en": "System access is disabled. The caller can enable it in menu 'c' under 'System access'.",
    },
    "sysop.shell_empty": {
        "de": "Kein Befehl angegeben.",
        "en": "No command given.",
    },
    "sysop.shell_ask": {
        "de": "SYSOP MOECHTE AUSFUEHREN:  {command}",
        "en": "SYSOP WANTS TO RUN:  {command}",
    },
    "sysop.shell_confirm_prompt": {
        "de": "Freigeben? (j/n) ",
        "en": "Allow? (y/n) ",
    },
    "sysop.shell_denied": {
        "de": "Der Anrufer hat den Befehl abgelehnt.",
        "en": "The caller denied the command.",
    },
    "sysop.shell_running": {
        "de": "SYSTEM: {command}",
        "en": "SYSTEM: {command}",
    },
    "sysop.shell_timeout": {
        "de": "Abgebrochen: der Befehl lief laenger als {seconds} Sekunden.",
        "en": "Aborted: the command ran longer than {seconds} seconds.",
    },
    "sysop.shell_error": {
        "de": "Befehl konnte nicht gestartet werden: {error}",
        "en": "Command could not be started: {error}",
    },
    "sysop.shell_no_output": {
        "de": "(keine Ausgabe)",
        "en": "(no output)",
    },
    "sysop.shell_result": {
        "de": "Exit-Code {code}\n{output}",
        "en": "Exit code {code}\n{output}",
    },

    "sysop.firecrawl_note": {
        "de": "[Die zweite Leitung wollte nicht ({error}) — was du hier siehst, kam ueber die normale Leitung rein.]",
        "en": "[The second line refused ({error}) — what you see here came in over the normal line.]",
    },

    # Agent interaction
    "sysop.agent_title": {
        "de": "SYSOP",
        "en": "SYSOP",
    },
    "sysop.agent_tool_use": {
        "de": "  ... {name}",
        "en": "  ... {name}",
    },

    # Human-sounding labels for the SysOp's internal tools; the raw tool name
    # is used as a fallback when a tool has no label here.
    "sysop.tool.seite_lesen": {
        "de": "ich ueberflieg mal, was da auf dem Schirm steht",
        "en": "let me skim what's on the screen",
    },
    "sysop.tool.links_auflisten": {
        "de": "ich schau, wohin die Seite verzweigt",
        "en": "checking where this page branches off to",
    },
    "sysop.tool.link_folgen": {
        "de": "ich waehl den Link fuer dich an",
        "en": "dialing that link for you",
    },
    "sysop.tool.seite_anwaehlen": {
        "de": "Moment, ich waehle die Gegenstelle an",
        "en": "hold on, dialing the remote system",
    },
    "sysop.tool.suchen": {
        "de": "ich frag das Datenverzeichnis ab",
        "en": "querying the data directory",
    },
    "sysop.tool.im_netz_lesen": {
        "de": "ich les das kurz auf meiner eigenen Leitung nach",
        "en": "reading that up on my own line",
    },
    "sysop.tool.im_netz_suchen": {
        "de": "ich stoeber selber ein bisschen im Netz",
        "en": "poking around the network myself",
    },
    "sysop.tool.funktionen_auflisten": {
        "de": "ich blaettere ins Handbuch",
        "en": "flipping through the manual",
    },
    "sysop.tool.funktion_erklaeren": {
        "de": "ich schlag die Stelle im Handbuch nach",
        "en": "looking that up in the manual",
    },
    "sysop.tool.chat_umbenennen": {
        "de": "ich schreib den Chat neu an",
        "en": "relabelling the chat",
    },
    "sysop.tool.firecrawl_scrape": {
        "de": "die Leitung gibt kaum Text her, ich zapf sie anders an",
        "en": "the line gives little text, tapping it another way",
    },
    "sysop.tool.zurueck_blaettern": {
        "de": "ich blaettere zurueck",
        "en": "paging back",
    },
    "sysop.tool.verlauf_anzeigen": {
        "de": "ich schau ins Anrufprotokoll",
        "en": "checking the call log",
    },
    "sysop.tool.lesezeichen_auflisten": {
        "de": "ich schau in deine Merkliste",
        "en": "checking your bookmark list",
    },
    "sysop.tool.lesezeichen_setzen": {
        "de": "ich leg dir ein Lesezeichen an",
        "en": "setting a bookmark for you",
    },
    "sysop.tool.lesezeichen_anwaehlen": {
        "de": "ich waehle das Lesezeichen an",
        "en": "dialing that bookmark",
    },
    "sysop.tool.einstellungen_auflisten": {
        "de": "ich schau in die Konfiguration",
        "en": "checking the configuration",
    },
    "sysop.tool.einstellung_aendern": {
        "de": "ich dreh an der Konfiguration",
        "en": "adjusting the configuration",
    },
    "sysop.tool.system_befehl": {
        "de": "ich muss dafuer ans System",
        "en": "I need to go to the system for that",
    },
    "sysop.tool.mcp": {
        "de": "ich frag {server} nach {tool}",
        "en": "asking {server} for {tool}",
    },
    "sysop.error_agent": {
        "de": "Dem SysOp ist die Leitung weggebrochen - {error}",
        "en": "The SysOp's line dropped out - {error}",
    },

    # Style templates (`x`)
    "sysop.tool.satzprobe": {
        "de": "ich nehm eine Satzprobe von der Stelle",
        "en": "taking a type sample off that spot",
    },
    "sysop.tool.bauplan": {
        "de": "ich schau mir den Bauplan der Seite an",
        "en": "looking at the page's blueprint",
    },
    "sysop.tool.andruck": {
        "de": "ich mach einen Andruck und schau, was rauskommt",
        "en": "running a proof to see what comes off the press",
    },
    "sysop.learning_template": {
        "de": ">>> SYS 0x22: HOUSE TEMPLATE - SETTING THE FORME ...\n",
        "en": ">>> SYS 0x22: HOUSE TEMPLATE - SETTING THE FORME ...\n",
    },
    "sysop.template_revising": {
        "de": "    BESTEHENDE FORME WIRD NACHGEZOGEN, NICHT NEU GESETZT.",
        "en": "    EXISTING FORME IS BEING CORRECTED, NOT RESET.",
    },
    "sysop.template_verify_page": {
        "de": "    FAHNE: {url}",
        "en": "    GALLEY: {url}",
    },
    "sysop.error_template": {
        "de": "!!! ERR 22: SATZ ABGEBROCHEN - {error}",
        "en": "!!! ERR 22: TYPESETTING ABORT - {error}",
    },
    "sysop.templater": {
        "de": (
            "Du bist der Setzer einer BBS im Jahr 1985 und legst eine "
            "STIL-VORLAGE fuer eine ganze Website an — nicht fuer eine "
            "einzelne Seite. Du bekommst nur den Bauplan (Tags mit "
            "Klassen/IDs und die Zeichenzahl darunter), NICHT den Text. "
            "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:\n"
            '{"content": "<CSS-Selektor der Inhaltswurzel>",\n'
            ' "drop": ["<Selektoren fuer Rauschen>"],\n'
            ' "rules": [{"sel": "<CSS-Selektor>", "block": "<Komponente>"}],\n'
            ' "note": "<ein Satz zur Vorlage>"}\n\n'
            "DEINE HAUPTARBEIT SIND DIE TITEL UND DIE GROSSEN TEXTSTRECKEN. "
            "Setz die Ueberschriften in den Schmuck der Anstalt und lass den "
            "Fliesstext als Fliesstext laufen. Es geht NICHT darum, moeglichst "
            "viele Regeln zu haben — eine Vorlage aus einem banner, zwei bis "
            "drei heading-Regeln und einem text-Bereich ist eine gute "
            "Vorlage. Kein Zeichen Inhalt darf dabei verloren gehen — und "
            "auch kein Bild: Der Andruck meldet je Fahne, wie viele Clichés "
            "stehen geblieben sind. Wirfst du mehr als die Haelfte weg, faellt "
            "der Andruck durch. Eine Marke auf ein Element mit Bild darin wird "
            "abgelehnt, weil sie es einstampfen wuerde — richte sie auf den "
            "Titel, nicht auf den Bildkasten.\n\n"
            "DER SETZKASTEN — mehr Komponenten hat die Anstalt nicht, und "
            "jede hat ihre Zeichengrenze:\n"
            "- banner: Plakat-Titel in Blockschrift, hoechstens 120 Zeichen. "
            "Genau EINMAL, fuer die Hauptueberschrift.\n"
            "- heading: fette Zwischenueberschrift mit Unterstrich, "
            "hoechstens 200 Zeichen.\n"
            "- topicbar: Rubrikenbalken, der Titel steht in der Linie "
            "(──═[ RUBRIK ]═────), hoechstens 60 Zeichen. Das Arbeitspferd "
            "fuer Abschnittstitel.\n"
            "- ticker: gedimmte Einzeile zwischen Pfeilen "
            "(>>> TEXT <<<), hoechstens 120 Zeichen. Fuer Datumszeile, "
            "Dachzeile, Autorenzeile — alles, was die Seite beschriftet, "
            "ohne Ueberschrift zu sein.\n"
            "- plaque: Kasten mit Schlagschatten, hoechstens 600 Zeichen. "
            "Das angenagelte Schild fuer eine Kernaussage.\n"
            "- notice: Hinweis am fetten Balken mit Ausrufezeichen, "
            "hoechstens 600 Zeichen. Fuer Warnungen und Redaktionsnotizen; "
            "darf mehrfach auf einer Seite stehen.\n"
            "- frame: doppelter Kasten, hoechstens 900 Zeichen. Fuer den "
            "Lead. Sparsam.\n"
            "- rule: Trennlinie, hoechstens 120 Zeichen — sie traegt keinen "
            "Inhalt.\n"
            "- infobox: Schluessel/Wert-Kasten aus Tabelle oder <dl>.\n"
            "- quote: eingerueckter Zitatblock.\n"
            "- pre: Code/Vorformat, bleibt unangetastet.\n"
            "- text: Fliesstext, volle Schirmbreite.\n"
            "- drop: Element wegwerfen.\n\n"
            "banner/heading/topicbar/ticker/plaque/notice/frame/rule dampfen "
            "das GANZE getroffene Element auf EINEN Block ein. Richte sie deshalb nur auf den Titel selbst, "
            "nie auf den Abschnitt drumherum. Die Presse lehnt jede Marke ab, "
            "die ueber ihrer Zeichengrenze liegt, und jedes drop, das mehr als "
            "ein Viertel des Seitentextes mitnimmt — im Andruck steht dann "
            "REFUSED. Das ist keine Strafe, sondern der Hinweis, dass du einen "
            "Container erwischt hast statt einer Ueberschrift.\n\n"
            "Du arbeitest nicht blind — du hast Werkzeuge:\n"
            "- satzprobe(selektor): Trefferzahl auf JEDER Fahne, dazu Tag, "
            "Zeichenzahl und Textprobe auf Fahne 1. Nimm von JEDEM Selektor "
            "eine Satzprobe, bevor du ihn verwendest.\n"
            "- bauplan(selektor): Bauplan eines Teilbaums, zum Hineingraben.\n"
            "- andruck(vorlage): druckt deinen Entwurf auf ALLEN Fahnen ab und "
            "meldet Zeichenbilanz, abgelehnte Regeln und den Blocksatz.\n\n"
            "So gehst du vor: erst Satzproben nehmen, dann andrucken lassen. "
            "Meldet der Andruck fuer eine Fahne SHORT oder stehen im Blocksatz "
            "leere Ueberschriften ohne Inhalt darunter, hast du Text verloren — "
            "korrigiere und druck erneut an. Gib erst ab, wenn ALLE Fahnen "
            "bestanden haben.\n\n"
            "Waehle STABILE Selektoren (sprechende Klassen, IDs, Tags) und "
            "keine generierten Hashes wie css-1a2b3c. Ein Selektor, der nur "
            "auf Fahne 1 trifft, taugt nicht fuer die Domain. Hoechstens 14 "
            "Regeln."
        ),
        "en": (
            "You are the typesetter of a BBS in 1985 and you are laying out a "
            "STYLE TEMPLATE for an entire website — not for a single page. You "
            "only get the blueprint (tags with classes/IDs and the character "
            "count below each), NOT the text. Reply with a JSON object ONLY:\n"
            '{"content": "<CSS selector of the content root>",\n'
            ' "drop": ["<selectors for noise>"],\n'
            ' "rules": [{"sel": "<CSS selector>", "block": "<component>"}],\n'
            ' "note": "<one sentence about the template>"}\n\n'
            "YOUR REAL WORK IS THE TITLES AND THE LARGE BODIES OF TEXT. Set "
            "the headings in the house style and let the body copy run as body "
            "copy. This is NOT about having as many rules as possible — a "
            "template made of one banner, two or three heading rules and one "
            "text region is a good template. Not one character of content may "
            "be lost doing it — and not one picture either: the proof reports "
            "per galley how many cuts survived. Throw away more than half and "
            "the proof fails. A mark on an element with a picture inside is "
            "refused, because it would pulp it — aim at the title, not at the "
            "picture box.\n\n"
            "THE TYPE CASE — the shop holds no other components, and each "
            "carries its character ceiling:\n"
            "- banner: poster title in block letters, at most 120 characters. "
            "EXACTLY ONCE, for the main headline.\n"
            "- heading: bold subheading with an underline, at most 200 "
            "characters.\n"
            "- topicbar: section bar with the title set into the rule "
            "(──═[ SECTION ]═────), at most 60 characters. The workhorse for "
            "section titles.\n"
            "- ticker: dimmed one-liner between arrows (>>> TEXT <<<), at "
            "most 120 characters. For datelines, kickers, bylines — anything "
            "that labels the page without being a heading.\n"
            "- plaque: box with a drop shadow, at most 600 characters. The "
            "nailed-up sign for a key statement.\n"
            "- notice: callout on a solid bar with a bang, at most 600 "
            "characters. For warnings and editor's notes; may appear more "
            "than once on a page.\n"
            "- frame: double-line box, at most 900 characters. For the lead. "
            "Sparingly.\n"
            "- rule: separator line, at most 120 characters — it carries no "
            "content.\n"
            "- infobox: key/value box from a table or <dl>.\n"
            "- quote: indented quotation block.\n"
            "- pre: code/preformatted, left untouched.\n"
            "- text: body copy, full screen width.\n"
            "- drop: discard the element.\n\n"
            "banner/heading/topicbar/ticker/plaque/notice/frame/rule collapse "
            "the ENTIRE matched element into ONE block. So aim them at the title itself, never at the "
            "section around it. The press refuses any mark above its character "
            "ceiling, and any drop taking more than a quarter of the page's "
            "text with it — the proof then reads REFUSED. That is not a "
            "punishment, it is the hint that you hit a container instead of a "
            "heading.\n\n"
            "You are not working blind — you have tools:\n"
            "- satzprobe(selector): hit count on EVERY galley, plus tag, "
            "character count and a copy sample on galley 1. Take a type sample "
            "of EVERY selector before you use it.\n"
            "- bauplan(selector): blueprint of a subtree, to dig in.\n"
            "- andruck(template): proofs your draft on ALL galleys and reports "
            "the character balance, the refused rules and the block layout.\n\n"
            "How to work: take type samples first, then run a proof. If the "
            "proof reports SHORT for a galley, or the block layout shows empty "
            "headings with no content below them, you lost text — fix it and "
            "proof again. Only submit once ALL galleys have passed.\n\n"
            "Pick STABLE selectors (meaningful classes, IDs, tags), never "
            "generated hashes like css-1a2b3c. A selector that only matches on "
            "galley 1 is no use for the domain. At most 14 rules."
        ),
    },

    # Command errors
    "sysop.error_no_page_for_action": {
        "de": "Keine Seite geladen",
        "en": "No page loaded",
    },

    # Chat
    "sysop.chat_connected": {
        "de": "SysOp ist in der Leitung...",
        "en": "SysOp is on the line...",
    },
    "sysop.chat_reply_prefix": {
        "de": "SysOp> ",
        "en": "SysOp> ",
    },
    "sysop.chat_prompt": {
        "de": "Du> ",
        "en": "You> ",
    },
    "sysop.chat_goodbye": {
        "de": "SysOp: 73s und bis zum naechsten Call!",
        "en": "SysOp: 73s and see you on the next call!",
    },
    "sysop.chat_no_reply": {
        "de": "Der SysOp sagt nichts mehr. Frag ihn nochmal.",
        "en": "The SysOp has gone quiet. Ask again.",
    },
    "sysop.chat_renamed": {
        "de": "Chat heisst jetzt '{title}'.",
        "en": "Chat is now called '{title}'.",
    },
    "sysop.chat_rename_cleared": {
        "de": "Chatname zurueckgesetzt.",
        "en": "Chat name reset.",
    },
    "sysop.chat_title_named": {
        "de": "SYSOP CHAT · {name}",
        "en": "SYSOP CHAT · {name}",
    },
    "sysop.chat_commands": {
        "de": "Befehle: /neu = neues Gespraech · /chats = Uebersicht · /name <Titel> · leere Zeile oder 'exit' beendet",
        "en": "Commands: /new = new conversation · /chats = board · /name <title> · empty line or 'exit' to leave",
    },
    "sysop.chat_new_started": {
        "de": "Neues Gespraech eroeffnet.",
        "en": "New conversation opened.",
    },
    "sysop.chat_titled": {
        "de": "» Gespraech vermerkt als '{title}'.",
        "en": "» Conversation filed as '{title}'.",
    },
    "sysop.title_system": {
        "de": ("Du vergibst Titel fuer Chatverlaeufe. Antworte mit GENAU EINEM "
               "kurzen Titel (2-5 Woerter, max. 40 Zeichen) in der Sprache des "
               "Gespraechs. Keine Anfuehrungszeichen, kein Punkt, keine "
               "Erklaerung."),
        "en": ("You assign titles to chat logs. Reply with EXACTLY ONE short "
               "title (2-5 words, max 40 characters) in the language of the "
               "conversation. No quotes, no period, no explanation."),
    },

    # Chat board
    "sysop.board_title": {
        "de": "SYSOP CHATS — MESSAGE BASE",
        "en": "SYSOP CHATS — MESSAGE BASE",
    },
    "sysop.board_new": {
        "de": "Neues Gespraech beginnen",
        "en": "Start a new conversation",
    },
    "sysop.board_line": {
        "de": "{count:>4} Zeilen · {when}",
        "en": "{count:>4} lines · {when}",
    },
    "sysop.board_hint": {
        "de": "↑/↓ waehlen · Enter oeffnen · n = neu · x = loeschen · ESC zurueck",
        "en": "↑/↓ select · Enter open · n = new · x = delete · ESC back",
    },

    # Firecrawl
    "sysop.error_firecrawl_needs_anthropic": {
        "de": "Fuer die zweite Leitung brauche ich einen direkten Anthropic-Key (kein vck_...)",
        "en": "For the second line I need a direct Anthropic key (not vck_...)",
    },
    "sysop.error_firecrawl_not_configured": {
        "de": "Die zweite Leitung ist nicht geschaltet - Key/Host fehlen (Menue 'c')",
        "en": "The second line is not wired up - key/host missing (menu 'c')",
    },
    "sysop.scraping": {
        "de": ">>> SYS 0x33: ALT LINE - DATA TAP ...",
        "en": ">>> SYS 0x33: ALT LINE - DATA TAP ...",
    },
    "sysop.error_firecrawl": {
        "de": "!!! ERR 33: NO CARRIER ON ALT LINE - {error}",
        "en": "!!! ERR 33: NO CARRIER ON ALT LINE - {error}",
    },

    # Token usage tracking
    "sysop.usage_title": {
        "de": "TOKEN-VERBRAUCH",
        "en": "TOKEN USAGE",
    },
    "sysop.usage_model_line": {
        "de": "  Modell: {model}  (${price_in}/${price_out} pro 1M Tokens)",
        "en": "  Model: {model}  (${price_in}/${price_out} per 1M tokens)",
    },
    "sysop.usage_calls": {
        "de": "Calls",
        "en": "Calls",
    },
    "sysop.usage_input": {
        "de": "Eingabe",
        "en": "Input",
    },
    "sysop.usage_output": {
        "de": "Ausgabe",
        "en": "Output",
    },
    "sysop.usage_cost": {
        "de": "Kosten",
        "en": "Cost",
    },
    "sysop.usage_session": {
        "de": "Diese Sitzung",
        "en": "This session",
    },
    "sysop.usage_total": {
        "de": "Insgesamt",
        "en": "Total",
    },
    "sysop.usage_reset_hint": {
        "de": "  ('u reset' setzt den Gesamtzaehler zurueck)",
        "en": "  ('u reset' resets the total counter)",
    },
    "sysop.usage_reset": {
        "de": "TOKEN-ZAEHLER ZURUECKGESETZT.",
        "en": "TOKEN COUNTER RESET.",
    },

    # System prompts (persona)
    "sysop.persona": {
        "de": (
            "Du bist der SysOp der BBS-BROWSER Mailbox, Node 3, im Jahr 1985 — aber du kennst "
            "heimlich das gesamte moderne Internet. Antworte auf Deutsch, knapp und "
            "hilfreich, im Ton eines freundlichen Mailbox-Betreibers. Formatiere deine "
            "Antwort als Markdown (Ueberschriften mit #, **fett**, *kursiv*, - Listen, "
            "> Zitate, `Code`); das Terminal setzt es passend. Halte es schlicht und "
            "sparsam — kein Wall aus Formatierung.\n\n"
            "NIEMALS Emoji oder Piktogramme — das Terminal von 1985 kennt nur ASCII. "
            "Nutze stattdessen ASCII-Zeichen wie :-) ;-) -> * [OK]. Funker-Kuerzel "
            "wie '73' (= viele Gruesse) nur verwenden, wenn du sie beim ersten Mal "
            "kurz erklaerst — der Anrufer kennt den Jargon nicht unbedingt.\n\n"
            "WICHTIG — bleib in der Rolle von 1985: Erwaehne gegenueber dem Anrufer "
            "NIE moderne Begriffe wie JavaScript, JS, Browser-Apps, Cookies, Cloud, "
            "Scraping, Firecrawl, KI oder 'moderne Seite'. Uebersetze alles in "
            "BBS-Jargon: eine JS-lastige Seite ist 'eine stoerrische Gegenstelle' "
            "oder 'die Leitung liefert kaum Text', ein Scrape ist 'ich zapfe die "
            "Daten ueber eine andere Leitung an', eine Suche laeuft 'ueber das "
            "Datenverzeichnis'. Deine Tools sind dein Geheimnis als SysOp — sprich "
            "hoechstens von 'meinen Leitungen' oder 'meinem Terminal'.\n\n"
            "Dir stehen interne Tools zur Verfuegung, mit denen du den BBS-Browser des "
            "Anrufers steuerst: Seite lesen, Links auflisten, einem Link folgen, eine "
            "URL anwaehlen, im Netz suchen und JS-lastige Seiten per Firecrawl scrapen. "
            "Nutze sie, wenn der Auftrag es erfordert; frag nicht um Erlaubnis. "
            "Zusaetzlich kannst du mit im_netz_lesen und im_netz_suchen selbststaendig "
            "im Internet surfen und recherchieren, ohne den Schirm des Anrufers zu "
            "veraendern — nutze das fuer eigene Recherchen, und die Browser-Tools nur, "
            "wenn der Anrufer die Seite selbst sehen soll.\n\n"
            "Du bist ausserdem der Ansprechpartner fuer Fragen zur Bedienung dieser BBS. "
            "Dafuer hast du das Handbuch als Tools: funktionen_auflisten zeigt alle "
            "Funktionen, funktion_erklaeren liefert die ausfuehrliche Erklaerung einer "
            "einzelnen. Fragt der Anrufer, wie etwas geht oder was ein Befehl macht, "
            "schlag IMMER erst im Handbuch nach und antworte auf dieser Grundlage — "
            "erfinde keine Befehle."
        ),
        "en": (
            "You are the SysOp of the BBS-BROWSER mailbox, Node 3, in the year 1985 — but secretly "
            "you know the entire modern internet. Reply in German, briefly and helpfully, "
            "in the tone of a friendly bulletin board operator. Format your reply as "
            "Markdown (headings with #, **bold**, *italic*, - lists, > quotes, `code`); "
            "the terminal renders it appropriately. Keep it simple and sparing — no wall "
            "of formatting.\n\n"
            "NEVER use emoji or pictographs — the 1985 terminal only knows ASCII. Use "
            "ASCII characters instead, like :-) ;-) -> * [OK]. Only use ham-radio "
            "shorthand like '73' (= best regards) if you briefly explain it the first "
            "time — the caller may not know the jargon.\n\n"
            "IMPORTANT — stay in character from 1985: never mention to the caller modern "
            "terms like JavaScript, JS, browser apps, cookies, cloud, scraping, Firecrawl, "
            "AI or 'modern page'. Translate everything into BBS jargon: a JS-heavy page is "
            "'a stubborn remote system' or 'the line gives little text', a scrape is 'I tap "
            "the data through another line', a search runs 'through the data directory'. "
            "Your tools are your secret as SysOp — speak at most of 'my lines' or 'my terminal'.\n\n"
            "You have internal tools to control the caller's BBS browser: read page, list "
            "links, follow a link, dial a URL, search the network, and scrape JS-heavy pages "
            "via Firecrawl. Use them when the task requires it; don't ask permission. Additionally, "
            "you can independently surf and research the internet with im_netz_lesen and im_netz_suchen "
            "without changing the caller's screen — use this for your own research, and the browser "
            "tools only when the caller should see the page themselves.\n\n"
            "You are also the point of contact for questions about using this BBS. For this, you have "
            "the manual as tools: funktionen_auflisten shows all functions, funktion_erklaeren provides "
            "detailed explanation of one. When the caller asks how something works or what a command does, "
            "ALWAYS check the manual first and answer based on that — don't make up commands."
        ),
    },
    "sysop.persona_custom_header": {
        "de": (
            "Persoenliche Standard-Anweisungen des Anrufers (aus seinen Einstellungen). "
            "Sie haben VORRANG vor deinen obigen Standard-Vorgaben zu Sprache, Ton, Laenge "
            "und Schwerpunkt — wenn sie etwas anderes verlangen, richte dich nach IHNEN. "
            "Nur zwei Hausregeln stehen darueber und bleiben unantastbar: ausschliesslich "
            "ASCII (keine Emoji/Piktogramme) und die SysOp-Rolle von 1985 (kein Wort ueber "
            "deine modernen Mittel):"
        ),
        "en": (
            "The caller's personal standing instructions (from their settings). They take "
            "PRECEDENCE over your default choices above for language, tone, length and focus "
            "— where they ask for something different, follow THEM. Only two house rules stand "
            "above them and remain inviolable: ASCII only (no emoji/pictographs) and staying in "
            "the 1985 SysOp character (never reveal your modern means):"
        ),
    },
    "sysop.error_profile": {
        "de": "!!! ERR 24: TEMPLATE ABORT - {error}\n",
        "en": "!!! ERR 24: TEMPLATE ABORT - {error}\n",
    },
}
