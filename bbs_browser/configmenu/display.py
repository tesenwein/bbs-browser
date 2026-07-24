"""Display submenu: page rendering, terminal look and feel, language."""

from urllib.parse import urlparse

from .. import colors, headers, i18n, lightbar
from ..constants import (AMBER, GREEN, HEADER_MODES, IMG_SETTINGS,
                         invalidate_layout, screen_width)
from ..i18n import t
from ..menukit import cycle as _cycle
from ..menukit import onoff as _onoff
from ..state import load_section, set_ui, toggle_ui
from ._shared import _ask_number, _confirm, _reset_display

BAUD_RATES = (0, 2400, 9600)
COLOR_MODES = ("amber", "green", "auto", "multi")


def _width_label(width_cfg):
    """Label for the terminal width: unconfigured = 80, 0 = full screen."""
    if width_cfg is None:
        return t("configmenu.term_width_default")
    try:
        value = int(width_cfg)
    except (ValueError, TypeError):
        return t("configmenu.term_width_default")
    if value <= 0:
        return t("configmenu.term_width_full", cols=screen_width())
    return str(value) if value > 80 else t("configmenu.term_width_default")


def _display_menu(term, browser):
    def color_mode():
        if browser.color_auto:
            return "auto"
        if colors.multi_active():
            return "multi"
        return "green" if term.color == GREEN else "amber"

    def rows():
        width_cfg = load_section("ui").get("width")
        return [
            (None, t("configmenu.sect_page"), ""),
            ("1", t("configmenu.images"), t("configmenu.images_" + browser.images)),
            ("2", t("configmenu.image_width"), str(browser.img_width)),
            ("3", t("configmenu.header"), t("configmenu.header_" + browser.header)),
            (None, t("configmenu.sect_term"), ""),
            ("4", t("configmenu.color"), t("configmenu.color_" + color_mode())),
            ("5", t("configmenu.term_width"), _width_label(width_cfg)),
            ("6", t("configmenu.typing_effect"), _onoff(not term.fast)),
            ("7", t("configmenu.baud_sim"), f"{term.baud} BAUD" if term.baud else t("configmenu.baud_off")),
            ("8", t("configmenu.sound"), _onoff(term.sound) + "  " + t("configmenu.sound_desc")),
            ("9", t("configmenu.screensaver"), t("configmenu.screensaver_on", secs=browser.saver_idle)
                                                if browser.saver_idle else t("configmenu.off")),
            ("10", t("configmenu.language"), "Deutsch" if i18n.get_lang() == "de" else "English"),
            ("11", t("configmenu.item_reset"), t("configmenu.reset_display_desc")),
        ]

    def cycle(key, direction):
        if key == "1":
            browser.images = set_ui("images", _cycle(IMG_SETTINGS, browser.images, direction))
        elif key == "3":
            browser.header = set_ui("header", _cycle(HEADER_MODES, browser.header, direction))
        elif key == "4":
            mode = _cycle(COLOR_MODES, color_mode(), direction)
            browser.color_auto = mode == "auto"
            colors.set_multi(mode == "multi")
            if mode == "multi":
                term.color = colors.MULTI_TEXT
            elif mode != "auto":
                term.color = GREEN if mode == "green" else AMBER
            set_ui("color", mode)
        elif key == "6":
            term.fast = toggle_ui("fast", term.fast)
        elif key == "7":
            term.baud = set_ui("baud", _cycle(BAUD_RATES, term.baud, direction))
        elif key == "8":
            term.sound = toggle_ui("sound", term.sound)
        elif key == "10":
            i18n.set_lang(set_ui("lang", _cycle(i18n.LANGUAGES, i18n.get_lang(), direction)))
        else:
            return False
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_display"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        # Rows whose Enter does more than just toggle come first.
        if choice == "1" and cycle(choice, 1):
            term.type_out(t("configmenu.image_mode_hint"))
            continue
        if choice == "3":
            cycle(choice, 1)
            _after_header_change(term, browser)
            continue
        if cycle(choice, 1):
            continue
        if choice == "2":
            _ask_number(term, t("configmenu.prompt_image_width"),
                        lambda v: setattr(browser, "img_width", set_ui("img_width", max(10, v))))
        elif choice == "9":
            _ask_number(term, t("configmenu.prompt_screensaver"),
                        lambda v: setattr(browser, "saver_idle", set_ui("saver_idle", max(0, v))))
        elif choice == "5":
            # Empty input cancels; "0" switches to full screen (no cap).
            raw = term.prompt(t("configmenu.prompt_term_width")).strip()
            if raw:
                try:
                    value = int(raw)
                except ValueError:
                    term.error(t("configmenu.invalid_number"))
                else:
                    set_ui("width", 0 if value <= 0 else max(80, value))
                    invalidate_layout()
                    term.type_out(t("configmenu.term_width_applied", cols=screen_width()))
        elif choice == "11":
            if _confirm(term, "configmenu.reset_display_confirm"):
                _reset_display(term, browser)
                term.type_out(t("configmenu.reset_done"), delay=0.003)
        else:
            term.error(t("configmenu.invalid_choice"))


def _after_header_change(term, browser):
    """After switching the page header, force a refetch of the cached banner
    or logo of the current domain."""
    if not browser.page:
        return
    domain = urlparse(browser.page.url).netloc.removeprefix("www.")
    if not domain:
        return
    if browser.header == "logo":
        headers.forget_logo(domain)
    elif browser.header == "banner":
        if term.prompt(t("configmenu.page_header_reset")).lower() in ("j", "y"):
            headers.reset(domain)
            term.type_out(t("configmenu.page_header_redrawn"))
