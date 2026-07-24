"""Uebersetzungskatalog fuer sysop_tools.py (Tool-Beschreibungen und
Rueckmeldungen an das Modell).

Achtung: Einstellungs-NAMEN und -WERTE (z.B. 'bilder', 'an', 'aus',
'blocks') sind Vertrag zwischen Modell und Code — sie bleiben in beiden
Sprachen woertlich erhalten."""

STRINGS = {
    # -- Runtime feedback returned to the model --
    "sysop_tools.function_not_found": {
        "de": "Keine Funktion '{name}' im Handbuch. Bekannt sind: {keys}",
        "en": "No function '{name}' in the manual. Known are: {keys}",
    },
    "sysop_tools.scrape_failed": {
        "de": "Scrape fehlgeschlagen oder Firecrawl nicht konfiguriert.",
        "en": "Scrape failed or Firecrawl not configured.",
    },
    "sysop_tools.history_empty": {
        "de": "Der Verlauf ist leer.",
        "en": "The history is empty.",
    },
    "sysop_tools.no_bookmarks": {
        "de": "Keine Lesezeichen vorhanden.",
        "en": "No bookmarks available.",
    },
    "sysop_tools.bookmark_set": {
        "de": "Lesezeichen gesetzt: {title} ({url})",
        "en": "Bookmark set: {title} ({url})",
    },
    "sysop_tools.color_allowed": {
        "de": "Erlaubt: green, amber, auto, multi.",
        "en": "Allowed: green, amber, auto, multi.",
    },
    "sysop_tools.lang_allowed": {
        "de": "Erlaubt: {list}.",
        "en": "Allowed: {list}.",
    },
    "sysop_tools.images_allowed": {
        "de": "Erlaubt: blocks (Halbbloecke), ascii, aus.",
        "en": "Allowed: blocks (half blocks), ascii, aus (pass these literals verbatim).",
    },
    "sysop_tools.header_allowed": {
        "de": "Erlaubt: logo, banner, aus.",
        "en": "Allowed: logo, banner, aus (pass these literals verbatim).",
    },
    "sysop_tools.setting_unknown": {
        "de": "Unbekannte Einstellung. Verfuegbar: {list}",
        "en": "Unknown setting. Available: {list}",
    },
    "sysop_tools.setting_invalid_value": {
        "de": "Ungueltiger Wert fuer '{name}' ({desc}).",
        "en": "Invalid value for '{name}' ({desc}).",
    },
    "sysop_tools.setting_changed": {
        "de": "Einstellung '{name}' auf '{value}' gesetzt.",
        "en": "Setting '{name}' set to '{value}'.",
    },

    # -- Settings map descriptions (value literals stay German — contract) --
    "sysop_tools.setting_bilder": {
        "de": "blocks/ascii/aus — Bilder auf Seiten (blocks = Halbbloecke)",
        "en": "blocks/ascii/aus — images on pages (blocks = half blocks; pass these literals verbatim)",
    },
    "sysop_tools.setting_bildbreite": {
        "de": "Zahl — Breite gerenderter Bilder in Zeichen (min. 10)",
        "en": "number — width of rendered images in characters (min. 10)",
    },
    "sysop_tools.setting_tipp_effekt": {
        "de": "an/aus — Text zeichenweise austippen",
        "en": "an/aus — type out text character by character (pass 'an' or 'aus' verbatim)",
    },
    "sysop_tools.setting_farbe": {
        "de": "green/amber/auto/multi — Phosphorfarbe des Terminals"
              " (multi = Rollenfarben im ANSI-BBS-Stil)",
        "en": "green/amber/auto/multi — phosphor color of the terminal"
              " (multi = role colors in ANSI BBS style)",
    },
    "sysop_tools.setting_baud": {
        "de": "Zahl — simulierte Baudrate, 0 = aus",
        "en": "number — simulated baud rate, 0 = off",
    },
    "sysop_tools.setting_sound": {
        "de": "an/aus — Modemgeraeusche und Signaltoene",
        "en": "an/aus — modem noises and signal tones (pass 'an' or 'aus' verbatim)",
    },
    "sysop_tools.setting_bildschirmschoner": {
        "de": "Sekunden — Leerlauf bis zum Schoner, 0 = aus",
        "en": "seconds — idle time until the screensaver, 0 = off",
    },
    "sysop_tools.setting_sprache": {
        "de": "de/en — Sprache der Oberflaeche",
        "en": "de/en — language of the interface",
    },
    "sysop_tools.setting_breite": {
        "de": "Zahl — Terminalbreite, 0 = Vollbild, sonst min. 80",
        "en": "number — terminal width, 0 = full screen, otherwise min. 80",
    },
    "sysop_tools.setting_seitenkopf": {
        "de": "logo/banner/aus — Kopfzeile ueber Seiten",
        "en": "logo/banner/aus — header above pages (pass these literals verbatim)",
    },

    # -- Tool descriptions and parameter descriptions --
    "sysop_tools.seite_lesen_desc": {
        "de": "Liest die aktuell im Browser geladene Seite (Titel, URL und kompletter Text).",
        "en": "Reads the page currently loaded in the browser (title, URL and full text).",
    },
    "sysop_tools.links_auflisten_desc": {
        "de": "Listet alle nummerierten Links der aktuell geladenen Seite mit Nummer, Beschriftung und Ziel-URL.",
        "en": "Lists all numbered links of the currently loaded page with number, label and target URL.",
    },
    "sysop_tools.link_folgen_desc": {
        "de": "Folgt dem Link mit der angegebenen Nummer auf der aktuellen Seite und laedt die Zielseite in den Browser.",
        "en": "Follows the link with the given number on the current page and loads the target page into the browser.",
    },
    "sysop_tools.link_folgen_param_nummer": {
        "de": "Die Link-Nummer aus links_auflisten (1-basiert).",
        "en": "The link number from links_auflisten (1-based).",
    },
    "sysop_tools.seite_anwaehlen_desc": {
        "de": "Waehlt eine URL an und laedt sie in den Browser des Anrufers.",
        "en": "Dials a URL and loads it into the caller's browser.",
    },
    "sysop_tools.seite_anwaehlen_param_url": {
        "de": "Die anzuwaehlende Adresse.",
        "en": "The address to dial.",
    },
    "sysop_tools.suchen_desc": {
        "de": "Sucht via DuckDuckGo und laedt die Ergebnisseite in den Browser.",
        "en": "Searches via DuckDuckGo and loads the results page into the browser.",
    },
    "sysop_tools.suchen_param_begriff": {
        "de": "Der Suchbegriff.",
        "en": "The search term.",
    },
    "sysop_tools.im_netz_lesen_desc": {
        "de": "Laedt eine URL im Hintergrund und liefert Titel, Text und Links zurueck, OHNE den Bildschirm des Anrufers zu veraendern. Nutze das zum eigenstaendigen Surfen und Recherchieren; seite_anwaehlen nur, wenn der Anrufer die Seite selbst sehen soll.",
        "en": "Loads a URL in the background and returns title, text and links WITHOUT changing the caller's screen. Use this for independent browsing and research; seite_anwaehlen only when the caller should see the page themselves.",
    },
    "sysop_tools.im_netz_lesen_param_url": {
        "de": "Die zu lesende Adresse.",
        "en": "The address to read.",
    },
    "sysop_tools.im_netz_suchen_desc": {
        "de": "Sucht via DuckDuckGo im Hintergrund und liefert die Treffer mit URLs zurueck, OHNE den Bildschirm des Anrufers zu veraendern. Ergebnisse danach bei Bedarf mit im_netz_lesen vertiefen.",
        "en": "Searches via DuckDuckGo in the background and returns the hits with URLs WITHOUT changing the caller's screen. Follow up on results with im_netz_lesen as needed.",
    },
    "sysop_tools.im_netz_suchen_param_begriff": {
        "de": "Der Suchbegriff.",
        "en": "The search term.",
    },
    "sysop_tools.funktionen_auflisten_desc": {
        "de": "Listet alle Funktionen und Befehle des BBS-Browsers mit Befehl, Syntax, Kategorie und Kurzbeschreibung. Nutze das, wenn der Anrufer wissen will, was der Browser kann.",
        "en": "Lists all functions and commands of the BBS browser with command, syntax, category and short description. Use this when the caller wants to know what the browser can do.",
    },
    "sysop_tools.funktion_erklaeren_desc": {
        "de": "Erklaert eine einzelne Funktion des BBS-Browsers ausfuehrlich. Nutze das immer, wenn der Anrufer fragt, wie etwas funktioniert oder was ein Befehl macht — antworte nie aus dem Gedaechtnis.",
        "en": "Explains a single function of the BBS browser in detail. Always use this when the caller asks how something works or what a command does — never answer from memory.",
    },
    "sysop_tools.funktion_erklaeren_param_name": {
        "de": "Befehl oder Stichwort, z.B. 'rss', 'l', 'chat', 'baud', 'firecrawl'.",
        "en": "Command or keyword, e.g. 'rss', 'l', 'chat', 'baud', 'firecrawl'.",
    },
    "sysop_tools.chat_umbenennen_desc": {
        "de": "Benennt den laufenden Chat um; der Name erscheint im Verlauf ('log'). Nutze das, wenn der Anrufer einen Namen wuenscht oder das Thema des Chats klar geworden ist.",
        "en": "Renames the current chat; the name appears in the history ('log'). Use this when the caller wants a name or the topic of the chat has become clear.",
    },
    "sysop_tools.chat_umbenennen_param_titel": {
        "de": "Kurzer Name fuer diesen Chat, max. 40 Zeichen. Leer laesst den Standardnamen zurueckkehren.",
        "en": "Short name for this chat, max. 40 characters. Empty restores the default name.",
    },
    "sysop_tools.firecrawl_scrape_desc": {
        "de": "Scraped eine JS-lastige Seite ueber Firecrawl und liefert das Markdown. Nur nutzen, wenn die normale Anwahl zu wenig Inhalt liefert.",
        "en": "Scrapes a JS-heavy page via Firecrawl and returns the Markdown. Only use this when the normal dial yields too little content.",
    },
    "sysop_tools.firecrawl_scrape_param_url": {
        "de": "Die zu scrapende Adresse.",
        "en": "The address to scrape.",
    },
    "sysop_tools.zurueck_blaettern_desc": {
        "de": "Blaettert im Browser des Anrufers eine Seite zurueck (wie der Befehl 'b').",
        "en": "Goes back one page in the caller's browser (like the 'b' command).",
    },
    "sysop_tools.verlauf_anzeigen_desc": {
        "de": "Listet die letzten 20 besuchten Seiten mit Nummer, Titel und URL.",
        "en": "Lists the last 20 visited pages with number, title and URL.",
    },
    "sysop_tools.lesezeichen_auflisten_desc": {
        "de": "Listet alle Lesezeichen des Anrufers mit Nummer, Titel und URL.",
        "en": "Lists all of the caller's bookmarks with number, title and URL.",
    },
    "sysop_tools.lesezeichen_setzen_desc": {
        "de": "Setzt ein Lesezeichen auf die aktuell geladene Seite.",
        "en": "Sets a bookmark on the currently loaded page.",
    },
    "sysop_tools.lesezeichen_anwaehlen_desc": {
        "de": "Waehlt ein Lesezeichen an und laedt es in den Browser des Anrufers.",
        "en": "Dials a bookmark and loads it into the caller's browser.",
    },
    "sysop_tools.lesezeichen_anwaehlen_param_nummer": {
        "de": "Die Nummer aus lesezeichen_auflisten (1-basiert).",
        "en": "The number from lesezeichen_auflisten (1-based).",
    },
    "sysop_tools.einstellungen_auflisten_desc": {
        "de": "Listet alle Einstellungen, die du fuer den Anrufer aendern darfst, mit erlaubten Werten. Immer zuerst aufrufen, bevor du eine Einstellung aenderst.",
        "en": "Lists all settings you may change for the caller, with allowed values. Always call this first before changing a setting.",
    },
    "sysop_tools.einstellung_aendern_desc": {
        "de": "Aendert eine unkritische Einstellung (Anzeige, Sound, Sprache, Baud usw.) fuer den Anrufer. API-Keys, Systemzugriff und MCP-Server kannst du NICHT aendern — dafuer den Anrufer ins Config-Menue ('c') schicken.",
        "en": "Changes a non-critical setting (display, sound, language, baud etc.) for the caller. You can NOT change API keys, system access or MCP servers — send the caller to the config menu ('c') for those.",
    },
    "sysop_tools.einstellung_aendern_param_name": {
        "de": "Name der Einstellung aus einstellungen_auflisten.",
        "en": "Name of the setting from einstellungen_auflisten (pass the German setting name verbatim).",
    },
    "sysop_tools.einstellung_aendern_param_wert": {
        "de": "Der neue Wert, z.B. 'an', 'aus', 'green', '9600', 'de'.",
        "en": "The new value, e.g. 'an', 'aus', 'green', '9600', 'de' (value literals stay German).",
    },
    "sysop_tools.system_befehl_desc": {
        "de": "Fuehrt einen Shell-Befehl auf dem Rechner des Anrufers aus und liefert Exit-Code und Ausgabe zurueck. Nutze das nur, wenn der Anrufer wirklich etwas am System wissen oder tun will. Sei sparsam und vorsichtig: keine zerstoerenden Befehle (rm -rf, Formatieren, Herunterfahren) ohne ausdruecklichen Auftrag, und keine interaktiven Programme, die auf Eingaben warten.",
        "en": "Runs a shell command on the caller's machine and returns exit code and output. Only use this when the caller really wants to know or do something on the system. Be sparing and careful: no destructive commands (rm -rf, formatting, shutting down) without an explicit request, and no interactive programs that wait for input.",
    },
    "sysop_tools.system_befehl_param_befehl": {
        "de": "Der auszufuehrende Shell-Befehl, z.B. 'uname -a' oder 'ls ~'.",
        "en": "The shell command to run, e.g. 'uname -a' or 'ls ~'.",
    },

    # -- Templater tools (the learning loop's print-shop metaphor) --
    "sysop_tools.satzprobe_desc": {
        "de": "Satzprobe zu einem CSS-Selektor: Trefferzahl auf JEDER Fahne, dazu Tag, Zeichenzahl und Textprobe auf Fahne 1. Damit erkennst du, ob ein Selektor eine Ueberschrift greift oder einen ganzen Inhaltsblock. Ein Selektor, der nur auf Fahne 1 trifft, taugt nicht fuer die Domain.",
        "en": "Type test for a CSS selector: hit count on EVERY galley, plus tag, character count and a text sample on galley 1. This tells you whether a selector grabs a heading or a whole content block. A selector that only matches on galley 1 is no good for the domain.",
    },
    "sysop_tools.satzprobe_param_selektor": {
        "de": "Der zu pruefende CSS-Selektor.",
        "en": "The CSS selector to test.",
    },
    "sysop_tools.bauplan_desc": {
        "de": "Bauplan eines Teilbaums: Tags mit Klassen/IDs und die Zeichenzahl darunter, ohne den Text. Ohne Selektor die ganze Fahne 1. Nutze das, um dich in einen Bereich hineinzugraben.",
        "en": "Blueprint of a subtree: tags with classes/IDs and the character count beneath them, without the text. Without a selector, the whole of galley 1. Use this to dig into an area.",
    },
    "sysop_tools.bauplan_param_selektor": {
        "de": "Optionaler CSS-Selektor der Wurzel.",
        "en": "Optional CSS selector of the root.",
    },
    "sysop_tools.andruck_desc": {
        "de": "Andruck deines Entwurfs auf ALLEN Fahnen: meldet je Fahne die Zeichenbilanz gegen den Handsatz, jede abgelehnte Regel und den Blocksatz von Fahne 1. Rufe das auf, BEVOR du fertig bist, und korrigiere, was danebengreift.",
        "en": "Proof print of your draft on ALL galleys: reports per galley the character balance against the hand-set baseline, every rejected rule and the full text block of galley 1. Call this BEFORE you finish, and correct whatever misses.",
    },
    "sysop_tools.andruck_param_vorlage": {
        "de": "Der Entwurf als JSON-Objekt (content/drop/rules/note).",
        "en": "The draft as a JSON object (content/drop/rules/note).",
    },
}
