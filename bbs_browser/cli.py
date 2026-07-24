"""Command line: arguments and entry point. The command loop lives in navigation.py."""

import argparse

from . import i18n
from .constants import AMBER, GREEN, IMG_MODES, RESET
from .i18n import t
from .browser import Browser
from .navigation import _looks_like_url, command_loop  # noqa: F401 — re-export
from .sysop import SysOp
from .terminal import Terminal, banner, modem_handshake
from .users import UserBase


def build_parser():
    p = argparse.ArgumentParser(prog="bbs", description=t("cli.description"))
    p.add_argument("url", nargs="?", help=t("cli.help_url"))
    p.add_argument("--fast", action="store_true", help=t("cli.help_fast"))
    p.add_argument("--green", action="store_true", help=t("cli.help_green"))
    p.add_argument("--firecrawl", action="store_true", help=t("cli.help_firecrawl"))
    p.add_argument("--no-handshake", action="store_true", help=t("cli.help_no_handshake"))
    p.add_argument("--no-images", action="store_true", help=t("cli.help_no_images"))
    p.add_argument("--img-width", type=int, help=t("cli.help_img_width"))
    p.add_argument("--img-mode", choices=IMG_MODES, help=t("cli.help_img_mode"))
    p.add_argument("--lang", choices=i18n.LANGUAGES, help=t("cli.help_lang"))
    p.add_argument("--links", action="store_true", help=t("cli.help_links"))
    return p


def list_links_only(url):
    """Tool mode: print the link list of a URL, exit code 1 on error."""
    from .page import fetch_page, normalize_url
    from .state import load_section

    page, err = fetch_page(normalize_url(url), load_section("firecrawl"), render_images=False)
    if err:
        print(f"NO CARRIER - {err}")
        return 1
    for i, (target, label) in enumerate(page.links, 1):
        print(f"[{i:>3}] {label}\n      {target}")
    return 0


def main():
    from .keys import init_console
    from .state import load_section

    init_console()  # Windows: ANSI escapes + UTF-8 output
    ui = load_section("ui")
    i18n.set_lang(ui.get("lang", i18n.DEFAULT_LANG))

    args = build_parser().parse_args()
    if args.lang:
        i18n.set_lang(args.lang)
    if args.links:
        if not args.url:
            build_parser().error(t("cli.error_links_needs_url"))
        raise SystemExit(list_links_only(args.url))

    # One-time migration of API keys from older versions into the keychain.
    from .sysop import migrate_keys
    migrate_keys()

    # Check in the background whether a new release is available — the
    # result lands in the cache and appears in the main menu (without
    # delaying startup).
    from .update import refresh_latest_async
    refresh_latest_async()

    color_mode = "green" if args.green else ui.get("color")
    if color_mode == "multi":
        from .colors import MULTI_TEXT, set_multi
        set_multi(True)
        color = MULTI_TEXT
    else:
        color = GREEN if color_mode == "green" else AMBER
    term = Terminal(
        color=color,
        fast=args.fast or ui.get("fast", False),
        baud=ui.get("baud", 9600),
        sound=ui.get("sound", False),
    )

    # Dial-in and login run with effects — Enter cuts them short.
    term.skippable = True

    if not args.no_handshake:
        modem_handshake(term)
    else:
        term.type_out(banner(), delay=0.0005)

    # Image setting: a single mode (blocks/ascii/off). Old separate keys
    # (images: bool + img_mode) are translated once on load.
    images = ui.get("images", True)
    if not isinstance(images, str):
        images = "off" if not images else ui.get("img_mode", "blocks")
    if args.no_images:
        images = "off"
    elif args.img_mode:
        images = args.img_mode
    browser = Browser(
        term,
        images=images,
        img_width=args.img_width or ui.get("img_width", 60),
    )
    if args.firecrawl:
        browser.firecrawl = {**browser.firecrawl, "enabled": True}
    sysop = SysOp(term, browser)
    browser.sysop = sysop
    browser.users = UserBase(term, sysop)

    # The SysOp writes his bulletins while the caller is still logging in.
    # In fast mode there is no dial-in sequence to hide the wait behind, so
    # the stored bulletins are simply reused until the next normal call.
    if not term.fast:
        from . import bulletins
        bulletins.refresh_async(sysop)

    # The weather station needs no key and no AI, so it runs in every mode.
    from . import weather
    weather.refresh_async()

    # Only log in now: the welcome box counts dialed-in AI callers, which
    # requires browser.users to already be set up.
    from .nostalgia import login
    # With a URL on the command line no board follows, so the login has to
    # print the welcome box itself.
    login(term, browser, board=not args.url)
    # Dial-in over: from here on keystrokes belong to the prompt again, and
    # the board is allowed to build up with effects even after a skip.
    term.skippable = False
    term.skip = False

    initial = None
    if args.url:
        browser.dial(args.url)
    else:
        from .nostalgia import main_board
        # Quick-dial via cursor delivers a command directly — otherwise the user is prompted.
        initial = main_board(term, browser)
        if not initial:
            url = term.prompt(t("cli.prompt_url_or_command"))
            if url and _looks_like_url(url):
                browser.dial(url)
            elif url:
                # Not URL-shaped? Then it was a command (e.g. 'fc' or 'c').
                initial = url

    try:
        command_loop(browser, sysop, initial)
    except (KeyboardInterrupt, EOFError):
        print(RESET + "\nNO CARRIER\n")
