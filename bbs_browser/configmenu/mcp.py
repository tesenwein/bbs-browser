"""MCP server submenus.

A list of custom MCP servers that the SysOp gets in addition to its
internal tools. The first level shows the list, the second level
maintains a single entry (URL, method, token or OAuth login).

Named like the top-level ``bbs_browser.mcp`` module on purpose — the
client module is always imported as ``from .. import mcp`` here, never
via a bare relative ``from . import mcp`` (which would hit this file).
"""

from .. import lightbar
from ..i18n import t
from ..menukit import cycle as _cycle
from ..menukit import onoff as _onoff


def _mcp_count_label():
    from .. import mcp
    servers = mcp.load_servers()
    if not servers:
        return t("configmenu.not_set")
    return t("configmenu.mcp_count", active=len(mcp.enabled_servers()), total=len(servers))


def _mcp_status_label(server):
    from .. import mcp
    return t("configmenu.mcp_status_" + mcp.status(server))


def _mcp_menu(term):
    from .. import mcp

    def rows():
        out = []
        for i, server in enumerate(mcp.load_servers(), 1):
            flag = "" if server.get("enabled", True) else t("configmenu.mcp_off_tag") + " "
            out.append((str(i), server.get("name", "?"),
                        flag + _mcp_status_label(server) + "  " + server.get("url", "")))
        out.append((None, t("configmenu.mcp_section_new"), ""))
        out.append(("n", t("configmenu.mcp_add"), t("configmenu.mcp_add_desc")))
        return out

    def toggle(key, _direction):
        servers = mcp.load_servers()
        if not key.isdigit() or not 1 <= int(key) <= len(servers):
            return False
        server = servers[int(key) - 1]
        server["enabled"] = not server.get("enabled", True)
        mcp.upsert(server)
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_mcp"), rows, on_cycle=toggle,
                               start=at, hint=t("configmenu.mcp_hint"))
        if not choice:
            return
        at = choice
        if choice == "n":
            name = _mcp_add(term)
            if name:
                _mcp_server_menu(term, name)
            continue
        servers = mcp.load_servers()
        if choice.isdigit() and 1 <= int(choice) <= len(servers):
            _mcp_server_menu(term, servers[int(choice) - 1]["name"])
        else:
            term.error(t("configmenu.invalid_choice"))


def _mcp_add(term):
    """Asks for URL and name and creates the entry. Returns the name."""
    from urllib.parse import urlparse

    from .. import mcp
    url = term.prompt(t("configmenu.prompt_mcp_url")).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    suggestion = mcp.unique_name(urlparse(url).netloc.removeprefix("www.").split(".")[0])
    name = mcp.unique_name(term.prompt(t("configmenu.prompt_mcp_name", name=suggestion)).strip()
                           or suggestion)
    mcp.upsert({"name": name, "url": url, "auth": "none", "enabled": True})
    return name


def _mcp_server_menu(term, name):
    from .. import mcp

    def rows():
        server = mcp.find(name) or {}
        auth = server.get("auth", "none")
        token = t("configmenu.mcp_token_set") if server.get("token") else t("configmenu.not_set")
        return [
            ("1", t("configmenu.mcp_url"), server.get("url", "")),
            ("2", t("configmenu.mcp_auth"), t("configmenu.mcp_auth_" + auth)),
            ("3", t("configmenu.mcp_token") if auth == "bearer" else t("configmenu.mcp_login"),
             token if auth != "none" else t("configmenu.mcp_auth_none")),
            ("4", t("configmenu.mcp_active"), _onoff(server.get("enabled", True))),
            ("5", t("configmenu.mcp_test"), _mcp_status_label(server)),
            ("6", t("configmenu.mcp_logout"), t("configmenu.mcp_logout_desc")),
            ("7", t("configmenu.mcp_delete"), ""),
        ]

    def cycle(key, direction):
        server = mcp.find(name)
        if not server:
            return False
        if key == "2":
            server["auth"] = _cycle(mcp.AUTH_MODES, server.get("auth", "none"), direction)
        elif key == "4":
            server["enabled"] = not server.get("enabled", True)
        else:
            return False
        mcp.upsert(server)
        return True

    at = "1"
    while True:
        server = mcp.find(name)
        if not server:
            return
        choice = lightbar.menu(term, t("configmenu.title_mcp_server", name=name), rows,
                               on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        server = mcp.find(name)
        if choice == "1":
            server["url"] = term.prompt(t("configmenu.prompt_mcp_url")).strip() or server["url"]
            mcp.upsert(server)
        elif choice == "3":
            if server.get("auth") == "bearer":
                server["token"] = term.prompt(t("configmenu.prompt_mcp_token")).strip()
                mcp.upsert(server)
            elif server.get("auth") == "oauth":
                _mcp_login(term, server)
            else:
                term.type_out(t("configmenu.mcp_auth_none_hint"), delay=0.003)
                term.pause()
        elif choice == "5":
            term.type_out(t("configmenu.mcp_testing"), delay=0.003)
            ok, reason = mcp.probe(server)
            if ok:
                term.type_out(t("configmenu.mcp_test_ok"), delay=0.003)
            else:
                term.error(t("configmenu.mcp_test_failed", reason=reason))
            term.pause()
        elif choice == "6":
            mcp.logout(server)
            term.type_out(t("configmenu.mcp_logged_out"), delay=0.003)
            term.pause()
        elif choice == "7":
            if term.prompt(t("configmenu.mcp_delete_confirm", name=name)).lower() in ("j", "y"):
                mcp.remove(name)
                return
        else:
            term.error(t("configmenu.invalid_choice"))


def _mcp_login(term, server):
    """OAuth login with progress messages on the terminal."""
    from .. import mcp

    def notify(step, **kwargs):
        term.type_out(t("configmenu.mcp_oauth_" + step, **kwargs), delay=0.002)

    ok, reason = mcp.login(server, notify=notify)
    if ok:
        term.type_out(t("configmenu.mcp_oauth_done"), delay=0.003)
    else:
        term.error(t("configmenu.mcp_oauth_failed", reason=reason))
