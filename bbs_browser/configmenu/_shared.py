"""Helpers shared by several configmenu submenus."""

from .. import colors, i18n
from ..constants import AMBER, invalidate_layout
from ..i18n import t
from ..state import clear_sections


def _confirm(term, key):
    return term.confirm(t(key))


def _reset_display(term, browser):
    """Anzeige-Einstellungen auf den Auslieferungszustand zuruecksetzen:
    Sektion loeschen (dann greifen wieder die Lade-Defaults) und dieselben
    Werte auf die laufenden Objekte anwenden."""
    clear_sections("ui")
    browser.images = "blocks"
    browser.img_width = 60
    browser.header = "logo"
    browser.auto_template = False
    browser.saver_idle = 300
    browser.color_auto = False
    colors.set_multi(False)
    term.color = AMBER
    term.fast = False
    term.baud = 9600
    term.sound = False
    i18n.set_lang(i18n.DEFAULT_LANG)
    invalidate_layout()


def _reset_all(term, browser):
    """Alle unkritischen Einstellungen zuruecksetzen — API-Keys, Passwort,
    Handle und MCP-Server bleiben unangetastet."""
    from .. import bulletins, weather

    _reset_display(term, browser)
    clear_sections(bulletins.SECTION, bulletins.CACHE_SECTION,
                   weather.SECTION, weather.CACHE_SECTION, "shell")


def _ask_number(term, prompt, apply):
    """Number prompt with a consistent error message."""
    try:
        apply(int(term.prompt(prompt) or 0))
    except ValueError:
        term.error(t("configmenu.invalid_number"))
