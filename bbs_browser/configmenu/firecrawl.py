"""Firecrawl submenu and the manual configuration check.

Named like the top-level ``bbs_browser.firecrawl`` module on purpose — the
client module is always imported as ``from ..firecrawl import ...`` here.
"""

from .. import lightbar
from ..constants import DIM, RESET
from ..fetch import normalize_base_url
from ..firecrawl import FIRECRAWL_CLOUD, firecrawl_check, firecrawl_reset
from ..i18n import t
from ..menukit import mask as _mask
from ..menukit import onoff as _onoff
from ..menukit import status_tag as _status_tag
from ..state import load_section, save_section


def run_firecrawl_check(term, fc, ai_key):
    # A manual check is an explicit "try again" — clear the session mute.
    firecrawl_reset()
    term.rule(t("configmenu.firecrawl_check_title"))
    term.type_out(t("configmenu.firecrawl_checking"), delay=0.003)
    for status, msg in firecrawl_check(fc, ai_key):
        tag = _status_tag(status)
        style = "" if status == "OK" else DIM
        print(term.color + style + f"  {tag} {msg}" + RESET)
    term.rule()
    term.pause()


def _firecrawl_menu(term, browser):
    from ..sysop_config import firecrawl_key, set_firecrawl_key

    def rows():
        fc = load_section("firecrawl")
        return [
            ("1", "Firecrawl", _onoff(fc.get("enabled"))),
            ("2", t("configmenu.mode"), t("configmenu.mode_mcp") if fc.get("use_mcp") else t("configmenu.mode_sdk")),
            ("3", t("configmenu.api_key"), _mask(firecrawl_key(fc))),
            ("4", t("configmenu.host"), fc.get("base_url") or t("configmenu.host_cloud", cloud=FIRECRAWL_CLOUD)),
            ("5", t("configmenu.firecrawl_check_item"), t("configmenu.firecrawl_check_item_desc")),
        ]

    def store(fc):
        save_section("firecrawl", fc)
        browser.firecrawl = fc
        # Changed settings deserve a fresh attempt — even if Firecrawl was
        # switched off for the session after repeated failures.
        firecrawl_reset()

    def cycle(key, _direction):
        fc = load_section("firecrawl")
        if key == "1":
            fc["enabled"] = not fc.get("enabled")
        elif key == "2":
            fc["use_mcp"] = not fc.get("use_mcp")
        else:
            return False
        store(fc)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_firecrawl"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        fc = load_section("firecrawl")
        if choice == "3":
            set_firecrawl_key(fc, term.prompt(t("configmenu.prompt_firecrawl_key")).strip())
        elif choice == "4":
            fc["base_url"] = normalize_base_url(term.prompt(t("configmenu.prompt_host")))
        elif choice == "5":
            # MCP needs the direct Anthropic key — check exactly that one.
            from ..sysop_config import config_key
            run_firecrawl_check(term, fc, config_key(load_section("ai"), "anthropic"))
            continue
        else:
            term.error(t("configmenu.invalid_choice"))
            continue
        store(fc)
