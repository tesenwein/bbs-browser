"""Navigation: the interactive command loop.

The command overview comes from manual.py — each function is documented
there exactly once, and help, the README table, and the SysOp tools all
draw from it.
"""

from .i18n import t
from . import manual
from .screensaver import matrix, prompt_with_saver



def _looks_like_url(text):
    return " " not in text and ("." in text or text.startswith(("http://", "https://")))


def command_loop(browser, sysop, initial=None):
    term = browser.term
    pending = initial
    while True:
        if pending:
            cmd = pending
            pending = None
        else:
            # Knocking happens before the prompt — this way the screensaver
            # is left untouched and only takes over the wait afterwards.
            if browser.users:
                browser.users.maybe_knock()
            hint = t("navigation.link_hint", num=len(browser.page.links)) if browser.page and browser.page.links else ""
            cmd = prompt_with_saver(
                term, hint + t("navigation.command_prompt"),
                browser.saver_idle,
            )
        if not cmd:
            continue
        parts = cmd.split(None, 1)
        op = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if op.isdigit():
            pending = browser.follow(int(op))
        elif op.startswith("/"):
            word = (op[1:] + (" " + arg if arg else "")).strip()
            pending = browser.find_in_page(word)
        elif op in ("d", "g", "dial"):
            url = arg or term.prompt(t("navigation.prompt_url"))
            if url.isdigit():
                pending = browser.dial_bookmark(int(url))
            elif url:
                pending = browser.dial(url)
        elif op in ("s", "search"):
            query = arg or term.prompt(t("navigation.prompt_search"))
            if query:
                pending = browser.search(query)
        elif op == "b":
            pending = browser.back()
        elif op == "f":
            pending = browser.forward()
        elif op == "r":
            pending = browser.reload()
        elif op == "x":
            from . import styletpl
            if not browser.page:
                term.error(t("browser.no_page_loaded"))
            elif not browser.template_ready():
                term.error(t("navigation.template_no_key"))
            elif not styletpl.eligible(browser.page):
                term.error(t("navigation.template_not_supported"))
            elif arg in ("-", "off", "aus", "del", "loeschen", "delete"):
                domain = styletpl.domain_of(browser.page.url)
                styletpl.delete(domain)
                term.type_out(t("navigation.template_deleted", domain=domain), delay=0.003)
                pending = browser.dial(browser.page.url, push_history=False)
            else:
                # Build or refresh: the learning loop needs the raw document
                # of the CURRENT page, so it works on the page as it stands.
                pending = browser.dial(browser.page.url, push_history=False,
                                       build_template=True)
        elif op == "l":
            pending = browser.list_links(arg)
        elif op == "n" and not arg:
            browser.list_nodes()
        elif op == "n" and arg.isdigit():
            pending = browser.switch_node(int(arg))
        elif op.startswith("n") and op[1:].isdigit():
            pending = browser.switch_node(int(op[1:]))
        elif op in ("fm", "form"):
            pending = browser.forms_menu(arg)
        elif op in ("bu", "bulletin", "bulletins"):
            pending = browser.show_bulletins(refresh=arg in ("r", "neu", "new"))
        elif op in ("we", "wetter", "weather"):
            pending = browser.show_weather(refresh=arg in ("r", "neu", "new"))
        elif op == "rss":
            pending = browser.show_feed(arg)
        elif op in ("o", "open"):
            browser.open_external(arg)
        elif op == "dl":
            browser.download(arg)
        elif op == "m":
            pending = browser.bookmark_menu()
        elif op == "home":
            from .nostalgia import main_board
            pending = main_board(term, browser)
        elif op == "a":
            browser.add_bookmark()
        elif op == "h":
            if arg.isdigit():
                pending = browser.dial_recent(int(arg))
            else:
                browser.show_history()
        elif op in ("sum", "summary"):
            sysop.summarize(browser.page)
        elif op == "ask":
            question = arg or term.prompt(t("navigation.prompt_question"))
            if question:
                sysop.ask(browser.page, question)
        elif op == "go":
            if not arg:
                term.error(t("navigation.error_go_usage"))
            elif _looks_like_url(arg):
                pending = browser.dial(arg)
            else:
                sysop.navigate(arg)
        elif op in ("sv", "matrix"):
            matrix(term)
        elif op in ("game", "games"):
            from .games import games_menu
            games_menu(term, arg)
        elif op in ("paddle", "stacker", "snake", "bricks"):
            from .games import games_menu
            games_menu(term, op)
        elif op == "dragon":
            from .games import games_menu
            games_menu(term, "dragon")
        elif op == "space":
            from .games import games_menu
            games_menu(term, "space")
        elif op == "chat":
            if arg.isdigit():
                # 'chat <nr>' resumes the conversation with that number from 'log'.
                from .chatlog import resume_by_number
                resume_by_number(term, browser, arg)
            elif arg.lower() in ("neu", "new", "n"):
                sysop.new_chat()
                sysop.chat()
            else:
                sysop.chat_board()
        elif op == "log":
            from .chatlog import run as show_chatlog
            show_chatlog(term, arg, browser)
        elif op == "w" and browser.users:
            browser.users.who()
        elif op == "p" and browser.users:
            browser.users.private_chat(arg)
        elif op == "ai":
            sysop.configure(arg)
        elif op == "u":
            if arg.lower() == "reset":
                sysop.reset_usage()
            else:
                sysop.show_usage()
        elif op == "fc":
            from .configmenu import run_firecrawl_check
            from .state import load_section
            from .sysop import config_key
            run_firecrawl_check(term, browser.firecrawl, config_key(load_section("ai"), "anthropic"))
        elif op == "c":
            from .configmenu import config_menu
            config_menu(term, browser, sysop)
        elif op == "i":
            from .constants import IMG_SETTINGS
            from .state import set_ui
            modes = list(IMG_SETTINGS)
            nxt = modes[(modes.index(browser.images) + 1) % len(modes)] \
                if browser.images in modes else modes[0]
            browser.images = set_ui("images", nxt)
            term.type_out(t("navigation.images_mode",
                            mode=t("configmenu.images_" + browser.images)), delay=0.003)
        elif op == "t":
            from .state import toggle_ui
            term.fast = toggle_ui("fast", term.fast)
            msg = t("navigation.typing_off") if term.fast else t("navigation.typing_on")
            term.type_out(msg, delay=0.003)
        elif op == "?":
            if arg:
                text = manual.explain(arg)
                if not text:
                    term.error(t("navigation.error_no_function", cmd=arg))
                else:
                    import textwrap
                    from .constants import screen_width
                    term.rule(t("navigation.handbook_title", cmd=arg))
                    for l in text.splitlines():
                        for w in textwrap.wrap(l, screen_width()) or [""]:
                            term.type_out(w, delay=0.001)
                    term.rule()
            else:
                # build it only here: the boxes are sized to this session's
                # actual terminal width. Routed through the pager so the
                # overview doesn't scroll off screen all at once.
                from .render import paginate
                term.clear()   # the overview takes over the screen like a menu
                resp = paginate(term, manual.overview_lines())
                if resp:
                    pending = resp
        elif op in ("up", "update"):
            from .update import run_update
            run_update(term)
        elif op == "q":
            # Only hang up after confirmation — otherwise a mistyped 'q'
            # would end the whole session.
            answer = (term.prompt(t("navigation.hangup_confirm")) or "").strip().lower()
            if answer not in ("j", "ja", "y", "yes"):
                continue
            term.type_out(t("navigation.hangup_message"), delay=0.02)
            from .state import save_state
            save_state(browser.bookmarks, browser.history)
            break
        else:
            term.error(t("navigation.error_unknown_command", cmd=op))
