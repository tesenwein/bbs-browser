"""Schluesselbund fuer API-Keys — damit sie nicht im Klartext in der DB liegen.

Die Keys wandern in den Schluesselbund des Betriebssystems (Gnome Keyring,
KWallet, macOS Keychain, Windows Credential Locker); in der Datenbank bleibt
nur die Marke ``<keyring>`` stehen. So sieht ein ``sqlite3 ~/.bbs_browser.db``
keine Geheimnisse mehr.

Gibt es kein nutzbares Backend (headless Linux ohne Keyring-Dienst, fehlendes
``keyring``-Paket), faellt alles still auf die alte Ablage in der DB zurueck —
die Mailbox laeuft dann genau wie vorher weiter.
"""

SERVICE = "bbs-browser"
MARK = "<keyring>"      # Platzhalter in der DB, wenn der echte Wert im Bund liegt

_backend = None         # None = noch nicht geprueft, False = keins, sonst Modul


def _keyring():
    """Das nutzbare keyring-Modul — oder False. Wird einmal pro Lauf geprobt."""
    global _backend
    if _backend is None:
        _backend = False
        try:
            import keyring
            keyring.set_password(SERVICE, "__probe__", "1")
            if keyring.get_password(SERVICE, "__probe__") == "1":
                _backend = keyring
            keyring.delete_password(SERVICE, "__probe__")
        except Exception:
            pass
    return _backend


def available():
    return bool(_keyring())


def get(slot):
    """Wert eines Slots aus dem Bund — "" wenn nichts da ist."""
    kr = _keyring()
    if not kr:
        return ""
    try:
        return kr.get_password(SERVICE, slot) or ""
    except Exception:
        return ""


def put(slot, value):
    """Wert ablegen. Liefert True, wenn er wirklich im Bund gelandet ist."""
    kr = _keyring()
    if not kr:
        return False
    try:
        kr.set_password(SERVICE, slot, value)
        return True
    except Exception:
        return False


def delete(slot):
    kr = _keyring()
    if not kr:
        return
    try:
        kr.delete_password(SERVICE, slot)
    except Exception:
        pass


def resolve(stored, slot):
    """Gespeicherten Wert aufloesen: Marke -> Bund, sonst der Wert selbst."""
    if stored == MARK:
        return get(slot)
    return stored or ""


def store(value, slot):
    """Wert wegschreiben und zurueckgeben, was in die DB gehoert: die Marke,
    wenn der Bund ihn genommen hat, sonst der Klartext wie bisher."""
    if not value:
        delete(slot)
        return ""
    if put(slot, value):
        return MARK
    return value
