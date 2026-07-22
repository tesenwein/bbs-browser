"""Uebersetzungskatalog fuer chatlog.py."""

STRINGS = {
    "chatlog.title": {"de": "CHATVERLAUF", "en": "CHAT LOG"},
    "chatlog.channel_sysop": {"de": "SYSOP", "en": "SYSOP"},
    "chatlog.empty": {"de": "Noch kein Chat gespeichert.", "en": "No chats stored yet."},
    "chatlog.line": {
        "de": "  {num:>2}) {name:<16} {count:>4} Zeilen   zuletzt {when}",
        "en": "  {num:>2}) {name:<16} {count:>4} lines   last {when}",
    },
    "chatlog.usage": {
        "de": "log <nr> = lesen · chat <nr> = fortsetzen · log del <nr> = loeschen · log clear = alles loeschen",
        "en": "log <no> = read · chat <no> = resume · log del <no> = delete · log clear = delete all",
    },
    "chatlog.resume_unavailable": {
        "de": "Dieser Verlauf laesst sich nicht fortsetzen.",
        "en": "This log cannot be resumed.",
    },
    "chatlog.error_bad_number": {"de": "Kein Verlauf mit Nummer {num}", "en": "No log with number {num}"},
    "chatlog.transcript_title": {"de": "VERLAUF · {name}", "en": "LOG · {name}"},
    "chatlog.you": {"de": "DU", "en": "YOU"},
    "chatlog.cleared_one": {"de": "Verlauf mit {name} geloescht.", "en": "Log with {name} deleted."},
    "chatlog.cleared_all": {"de": "Alle Chatverlaeufe geloescht.", "en": "All chat logs deleted."},
}
