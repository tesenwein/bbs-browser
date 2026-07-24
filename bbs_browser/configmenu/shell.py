"""Shell access submenu: SysOp's system access mode and timeout."""

from .. import lightbar
from ..i18n import t
from ..menukit import cycle as _cycle
from ..state import load_section, save_section
from ._shared import _ask_number


def _shell_mode_label():
    from ..sysop_config import shell_config
    return t("configmenu.shell_mode_" + shell_config()[0])


def _shell_menu(term):
    """SysOp's system access: off / with confirmation / free, plus timeout."""
    from ..sysop_config import SHELL_MODES, shell_config

    def rows():
        mode, timeout = shell_config()
        return [
            ("1", t("configmenu.shell_mode"), t("configmenu.shell_mode_" + mode)),
            ("2", t("configmenu.shell_timeout"), t("configmenu.shell_timeout_value", seconds=timeout)),
        ]

    def cycle(key, direction):
        if key != "1":
            return False
        shell = load_section("shell")
        shell["mode"] = _cycle(SHELL_MODES, shell_config()[0], direction)
        save_section("shell", shell)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_shell"), rows, on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if choice == "1":
            # Only warn when switching it on — 'free' runs without any confirmation.
            cycle(choice, 1)
            if shell_config()[0] == "free":
                term.type_out(t("configmenu.shell_free_warning"), delay=0.003)
            continue
        if choice == "2":
            def _timeout(v):
                shell = load_section("shell")
                shell["timeout"] = max(1, v)
                save_section("shell", shell)
            _ask_number(term, t("configmenu.prompt_shell_timeout"), _timeout)
        else:
            term.error(t("configmenu.invalid_choice"))
