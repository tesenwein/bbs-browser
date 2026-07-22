"""Zweisprachigkeit (DE/EN): zentrale t()-Funktion und Sprachumschaltung.

Jedes Modul mit UI-Text hat eine eigene strings_<modul>.py mit einem
STRINGS-Dict ({"schluessel": {"de": "...", "en": "..."}}). Hier werden
alle Kataloge zusammengefuehrt und ueber t(schluessel, **kwargs) abgerufen.
"""

from .strings_browser import STRINGS as _S_BROWSER
from .strings_bulletins import STRINGS as _S_BULLETINS
from .strings_chatlog import STRINGS as _S_CHATLOG
from .strings_cli import STRINGS as _S_CLI
from .strings_configmenu import STRINGS as _S_CONFIGMENU
from .strings_dragon import STRINGS as _S_DRAGON
from .strings_feeds import STRINGS as _S_FEEDS
from .strings_games import STRINGS as _S_GAMES
from .strings_images import STRINGS as _S_IMAGES
from .strings_lightbar import STRINGS as _S_LIGHTBAR
from .strings_manual import STRINGS as _S_MANUAL
from .strings_navigation import STRINGS as _S_NAVIGATION
from .strings_nostalgia import STRINGS as _S_NOSTALGIA
from .strings_page import STRINGS as _S_PAGE
from .strings_render import STRINGS as _S_RENDER
from .strings_retronet import STRINGS as _S_RETRONET
from .strings_screensaver import STRINGS as _S_SCREENSAVER
from .strings_styletpl import STRINGS as _S_STYLETPL
from .strings_sysop import STRINGS as _S_SYSOP
from .strings_terminal import STRINGS as _S_TERMINAL
from .strings_update import STRINGS as _S_UPDATE
from .strings_users import STRINGS as _S_USERS
from .strings_weather import STRINGS as _S_WEATHER

ALL_STRINGS = {}
for _catalog in (
    _S_STYLETPL,
    _S_BROWSER, _S_BULLETINS, _S_CHATLOG, _S_CLI, _S_CONFIGMENU, _S_DRAGON, _S_FEEDS, _S_GAMES, _S_IMAGES,
    _S_LIGHTBAR, _S_MANUAL,
    _S_NAVIGATION, _S_NOSTALGIA, _S_PAGE, _S_RENDER, _S_RETRONET,
    _S_SCREENSAVER, _S_SYSOP, _S_TERMINAL, _S_UPDATE, _S_USERS, _S_WEATHER,
):
    ALL_STRINGS.update(_catalog)

LANGUAGES = ("de", "en")
DEFAULT_LANG = "en"
_lang = DEFAULT_LANG


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGUAGES else DEFAULT_LANG
    return _lang


def get_lang():
    return _lang


def t(key, **kwargs):
    """Liefert den uebersetzten Text zu `key` in der aktuellen Sprache.

    Fehlt der Schluessel oder die Sprache, wird auf Englisch bzw. den
    Schluessel selbst zurueckgefallen (Sicherheitsnetz, kein Crash im UI)."""
    entry = ALL_STRINGS.get(key)
    if entry is None:
        return key
    if _lang in entry:
        text = entry[_lang]
    elif DEFAULT_LANG in entry:
        text = entry[DEFAULT_LANG]
    else:
        text = key
    return text.format(**kwargs) if kwargs else text
