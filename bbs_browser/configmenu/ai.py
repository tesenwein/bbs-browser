"""AI SysOp submenu: provider, key, model, prompt and style templates."""

from .. import db, lightbar
from ..i18n import t
from ..menukit import cycle as _cycle
from ..menukit import mask as _mask
from ..menukit import onoff as _onoff
from ..state import load_section, save_section, toggle_ui
from ._shared import _confirm


def _prompt_preview(ai):
    """Short preview of the default prompt for the menu row."""
    text = " ".join((ai.get("prompt") or "").split())
    if not text:
        return t("configmenu.not_set")
    return (text[:37] + "…") if len(text) > 38 else text


def _ai_menu(term, browser, sysop):
    from ..sysop_config import (PROVIDERS, active_provider, config_key,
                                provider_label, set_config_key)

    def rows():
        ai = load_section("ai")
        provider = active_provider(ai)
        return [
            ("1", t("configmenu.provider"), provider_label(provider)),
            ("2", t("configmenu.api_key"), _mask(config_key(ai, provider))),
            ("3", t("configmenu.model"), ai.get("model") or t("configmenu.model_default")),
            ("4", t("configmenu.sysop_prompt"), _prompt_preview(ai)),
            ("5", t("configmenu.templates"), _template_summary()),
        ]

    def cycle(key, direction):
        if key == "1":
            ai = load_section("ai")
            ai["provider"] = _cycle(PROVIDERS, active_provider(ai), direction)
            save_section("ai", ai)
            sysop._client = None
        else:
            return False
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_ai"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        ai = load_section("ai")
        provider = active_provider(ai)
        if choice == "2":
            set_config_key(ai, provider, term.prompt(t("configmenu.prompt_api_key")).strip())
            save_section("ai", ai)
            sysop._client = None
        elif choice == "3":
            ai["model"] = term.prompt(t("configmenu.prompt_model"))
            save_section("ai", ai)
            sysop._client = None
        elif choice == "4":
            current = (ai.get("prompt") or "").strip()
            if current:
                term.type_out(t("configmenu.sysop_prompt_current", prompt=current), delay=0.002)
            text = term.prompt(t("configmenu.prompt_sysop_prompt")).strip()
            if text == "-":
                ai.pop("prompt", None)
                save_section("ai", ai)
                term.type_out(t("configmenu.sysop_prompt_cleared"), delay=0.003)
            elif text:
                ai["prompt"] = text
                save_section("ai", ai)
                term.type_out(t("configmenu.sysop_prompt_saved"), delay=0.003)
        elif choice == "5":
            _template_menu(term, browser)
        else:
            term.error(t("configmenu.invalid_choice"))


def _template_summary():
    """Short status for the AI menu row: how many domains carry a learned
    style template, and whether the automatic mode is on."""
    n = len(db.templates())
    auto = load_section("ui").get("auto_template", False)
    if not n:
        return t("configmenu.templates_auto_only" if auto else "configmenu.not_set")
    return t("configmenu.templates_summary", n=n,
             auto=t("configmenu.on" if auto else "configmenu.off"))


def _template_menu(term, browser):
    """Learned style templates: toggle the auto-LEARNING, delete a single
    domain's template, or throw them all away. Applying is not a setting —
    a stored template is always used where it grips; the switch here only
    decides whether unknown domains get one learned on first visit.
    Building/refreshing happens with 'x' on the page itself — that's where
    the document is."""
    def rows():
        stored = db.templates()
        rows = [("a", t("configmenu.templates_autolearn"),
                 _onoff(browser.auto_template)),
                (None, t("configmenu.templates_always_used"), "")]
        for i, tpl in enumerate(stored, 1):
            rows.append((str(i), tpl["domain"],
                         t("configmenu.templates_row_hint", n=tpl["verified"])))
        if stored:
            rows.append(("0", t("configmenu.templates_clear"), ""))
        return rows

    at = "a"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_templates"), rows, start=at)
        if not choice:
            return
        at = choice
        if choice == "a":
            browser.auto_template = toggle_ui("auto_template", browser.auto_template)
            continue
        templates = db.templates()
        if choice == "0":
            if templates and _confirm(term, "configmenu.templates_clear_confirm"):
                db.template_clear()
                term.type_out(t("configmenu.templates_cleared"), delay=0.003)
            continue
        idx = int(choice) - 1 if choice.isdigit() else -1
        if not (0 <= idx < len(templates)):
            term.error(t("configmenu.invalid_choice"))
            continue
        domain = templates[idx]["domain"]
        if term.confirm(t("configmenu.templates_delete_confirm", domain=domain)):
            db.template_delete(domain)
            term.type_out(t("configmenu.templates_deleted", domain=domain), delay=0.003)
            # The numbering shifts after a delete — back to a stable anchor.
            at = "a"
