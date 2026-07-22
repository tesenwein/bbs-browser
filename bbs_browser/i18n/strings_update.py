"""Uebersetzungskatalog fuer update.py (Selbst-Update, Befehl 'up')."""

STRINGS = {
    "update.title": {"de": "SYSTEM-UPDATE", "en": "SYSTEM UPDATE"},
    "update.current": {
        "de": "Aktuelle Version: {version}",
        "en": "Current version: {version}",
    },
    "update.checking": {
        "de": ">> Suche nach neuer Version ...",
        "en": ">> Checking for a new version ...",
    },
    "update.tool_missing": {
        "de": "{tool} nicht gefunden.",
        "en": "{tool} not found.",
    },
    "update.no_release": {
        "de": "Keine Release gefunden (Netz? Noch keine Veroeffentlichung?).",
        "en": "No release found (network? nothing published yet?).",
    },
    "update.up_to_date": {
        "de": "Schon aktuell — Version {version}.",
        "en": "Already up to date — version {version}.",
    },
    "update.found": {
        "de": "Neue Version verfuegbar: {version}",
        "en": "New version available: {version}",
    },
    "update.no_asset": {
        "de": "Release {version} enthaelt kein installierbares Paket (.whl).",
        "en": "Release {version} has no installable package (.whl).",
    },
    "update.downloading": {
        "de": ">> Lade {name} ...",
        "en": ">> Downloading {name} ...",
    },
    "update.download_failed": {
        "de": "Download fehlgeschlagen — siehe Netzverbindung.",
        "en": "Download failed — check your network connection.",
    },
    "update.installing_pipx": {
        "de": ">> Installiere via pipx ...",
        "en": ">> Installing via pipx ...",
    },
    "update.installing_pip": {
        "de": ">> Installiere via pip ...",
        "en": ">> Installing via pip ...",
    },
    "update.install_failed": {
        "de": "Installation fehlgeschlagen — siehe Ausgabe oben.",
        "en": "Installation failed — see output above.",
    },
    "update.done": {
        "de": "OK — Version {version} installiert.",
        "en": "OK — version {version} installed.",
    },
    "update.restart_hint": {
        "de": "Bitte 'bbs' neu starten, damit die neue Version laeuft.",
        "en": "Please restart 'bbs' for the new version to take effect.",
    },
    # Hinweis im Hauptmenue, wenn eine neue Release bereitsteht.
    "update.board_hint": {
        "de": "Update verfuegbar: {version} — 'up' eingeben zum Aktualisieren.",
        "en": "Update available: {version} — type 'up' to update.",
    },
}
