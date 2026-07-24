"""Interactive configuration menu (command 'k') — nested by topic.

All submenus run through the same lightbar component: cursor up/down
selects, left/right toggles the row's value directly, Enter opens or
advances — and the old numeric hotkeys still work unchanged.

Split into one submodule per topic; this package module keeps the main
dispatcher and re-exports everything external callers (and the tests)
reach via ``bbs_browser.configmenu``.
"""

from .. import lightbar
from ..i18n import t
from ..state import load_section

from ._shared import _ask_number, _confirm, _reset_all, _reset_display
from .ai import _ai_menu, _prompt_preview, _template_menu, _template_summary
from .bulletins import (_bulletin_menu, _bulletin_sources_menu,
                        _bulletin_summary, _source_kind_label, _ttl_label)
from .display import (BAUD_RATES, COLOR_MODES, _after_header_change,
                      _display_menu, _width_label)
from .firecrawl import _firecrawl_menu, run_firecrawl_check
from .mcp import (_mcp_add, _mcp_count_label, _mcp_login, _mcp_menu,
                  _mcp_server_menu, _mcp_status_label)
from .shell import _shell_menu, _shell_mode_label
from .weather import _weather_menu, _weather_place_prompt, _weather_summary


def config_menu(term, browser, sysop):
    def rows():
        prof = load_section("profile")
        pw_state = t("configmenu.pw_set_tag") if prof.get("pw_hash") else t("configmenu.not_set")
        return [
            ("1", t("configmenu.item_ai_sysop"), t("configmenu.item_ai_sysop_desc")),
            ("2", "Firecrawl", t("configmenu.item_firecrawl_desc")),
            ("3", t("configmenu.item_display"), t("configmenu.item_display_desc")),
            ("4", t("configmenu.item_password"), pw_state + "  " + t("configmenu.item_password_desc")),
            ("5", t("configmenu.item_handle"),
             (prof.get("handle") or "-") + "  " + t("configmenu.item_handle_desc")),
            ("6", t("configmenu.item_shell"),
             _shell_mode_label() + "  " + t("configmenu.item_shell_desc")),
            ("7", "MCP", _mcp_count_label() + "  " + t("configmenu.item_mcp_desc")),
            ("8", t("configmenu.item_weather"), _weather_summary()),
            ("9", t("configmenu.bulletins"), _bulletin_summary()),
            # Reset sits on '0', not '10': a two-character key would make '1'
            # ambiguous and cost every entry its instant hotkey.
            ("0", t("configmenu.item_reset"), t("configmenu.item_reset_desc")),
        ]

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_main"), rows, start=at)
        if not choice:
            return
        at = choice
        if choice == "1":
            _ai_menu(term, browser, sysop)
        elif choice == "2":
            _firecrawl_menu(term, browser)
        elif choice == "3":
            _display_menu(term, browser)
        elif choice == "4":
            from ..nostalgia import change_password
            change_password(term)
        elif choice == "5":
            from ..nostalgia import change_handle
            change_handle(term)
        elif choice == "6":
            _shell_menu(term)
        elif choice == "7":
            _mcp_menu(term)
        elif choice == "8":
            _weather_menu(term)
        elif choice == "9":
            _bulletin_menu(term, sysop)
        elif choice == "0":
            if _confirm(term, "configmenu.reset_all_confirm"):
                _reset_all(term, browser)
                term.type_out(t("configmenu.reset_done"), delay=0.003)
        else:
            term.error(t("configmenu.invalid_choice"))
