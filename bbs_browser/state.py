"""Persistenz fuer Bookmarks, Verlauf und Konfiguration.

Liegt seit der SQLite-Umstellung in ~/.bbs_browser.db (siehe db.py); die
Schnittstelle hier ist unveraendert, damit die aufrufenden Module nichts
ueber die Ablage wissen muessen.
"""

from . import db


def load_state():
    nav = db.get_section("nav")
    return nav.get("bookmarks", []), nav.get("history", [])


def save_state(bookmarks, history):
    db.set_section("nav", {"bookmarks": bookmarks, "history": history[-100:]})


def load_section(name):
    """Beliebige Config-Sektion ("ai", "firecrawl", "ui")."""
    data = db.get_section(name)
    return data if isinstance(data, dict) else {}


def save_section(name, cfg):
    db.set_section(name, cfg)


def set_ui(key, value):
    """Eine einzige Stelle zum Speichern von Anzeige-/Modus-Einstellungen."""
    ui = load_section("ui")
    ui[key] = value
    save_section("ui", ui)
    return value


def toggle_ui(key, current):
    """Schaltet eine Einstellung um und speichert sie. Liefert den neuen Wert."""
    return set_ui(key, not current)


def clear_sections(*names):
    """Loescht Config-Sektionen komplett — die Lade-Defaults greifen wieder."""
    for name in names:
        save_section(name, {})


def load_ai_config():
    return load_section("ai")


def save_ai_config(cfg):
    save_section("ai", cfg)
