"""Browser state: current page, navigation, bookmarks, history."""

import re
from urllib.parse import urlparse

from . import headers, lightbar
from .colors import pick_color
from .constants import DIM, RESET, USER_AGENT, screen_width
from .i18n import t
from .firecrawl import firecrawl_muted, firecrawl_search
from .fetch import (
    ddg_search, fetch_page, normalize_base_url, normalize_url,
    page_from_search_results,
)
from .page import page_from_markdown, page_text
from .render import layout_page, paginate
from .state import load_section, load_state, save_state

MAX_NODES = 4
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def open_in_system_browser(url):
    """Hand a URL to the real browser. Returns True if a handler took it.

    webbrowser alone is not enough: under WSL and on bare SSH sessions it
    reports success without a browser ever appearing, so the platform
    openers get their turn first.
    """
    import shutil
    import subprocess
    for opener in ("wslview", "xdg-open", "open", "explorer.exe"):
        if not shutil.which(opener):
            continue
        try:
            subprocess.Popen([opener, url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    try:
        import webbrowser
        return webbrowser.open(url)
    except Exception:
        return False


class Browser:
    def __init__(self, term, images="blocks", img_width=60):
        self.term = term
        self.firecrawl = load_section("firecrawl")
        self.images = images   # images: "blocks" (half-blocks) / "ascii" / "off"
        self.img_width = img_width
        self.sysop = None
        self.users = None      # AI callers ('w' / 'p <nr>'), set by cli.py
        ui = load_section("ui")
        self.color_auto = ui.get("color") == "auto"
        # Page header: "logo" (real page logo, banner as fallback) /
        # "banner" (random banner per domain) / "off". Old single toggles
        # (page_header/logo_header) are translated once on load.
        self.header = ui.get("header") or (
            "off" if not ui.get("page_header", True)
            else "banner" if not ui.get("logo_header", True) else "logo")
        # Style templates: build one automatically the first time a domain
        # is visited, or only on demand via 'x'. Off by default — learning
        # costs AI calls, and that shouldn't happen behind the user's back.
        self.auto_template = ui.get("auto_template", False)
        self.saver_idle = ui.get("saver_idle", 300)   # seconds idle until matrix rain, 0 = off
        self.page = None
        # History stacks hold finished Page objects, not URLs: back/forward
        # shows exactly the page that was seen (incl. AI layout and
        # scrape touch-up), without a new fetch — even if the server
        # is no longer reachable in the meantime.
        self.back_stack = []
        self.forward_stack = []
        self.bookmarks, self.history = load_state()
        # Nodes ("Tabs"): each line has its own page + history.
        self.nodes = [None] * MAX_NODES
        self.node_idx = 0
        self._find_word = ""
        self._find_pos = -1
        self._logo_domain = None   # domain whose logo was last shown in the header

    # Derived views of the images setting — the renderers still only
    # know "on/off" plus one character mode.
    @property
    def render_images(self):
        return self.images != "off"

    @property
    def img_mode(self):
        return self.images if self.images != "off" else "blocks"

    # -- Loading ----------------------------------------------------------

    def dial(self, url, push_history=True, build_template=False):
        term = self.term
        url = normalize_url(url)
        from . import styletpl
        template = styletpl.load(url)
        try:
            term.type_out("\n" + t("browser.dialing", url=url), delay=0.02)
            if self.render_images:
                term.type_out(t("browser.loading_graphics"), delay=0.01)
            page, err = fetch_page(url, self.firecrawl, self.render_images,
                                   self.img_width, self.img_mode, template)
            if err:
                term.error(t("browser.no_carrier", err=err))
                return None
            # Emergency brake: a template that leaves the page threadbare
            # tore it apart instead of styling it — then the heuristic gets
            # the page back. The template stays: it may fit the next page.
            braked = False
            if template and page.low_text and page.html:
                try:
                    from .page import build_page
                    plain = build_page(page.html, page.url, self.render_images,
                                       self.img_width, self.img_mode,
                                       js_rendered=getattr(page, "js_rendered", None))
                except Exception:
                    plain = None
                if plain is not None and not plain.low_text:
                    term.error(t("styletpl.fit_failed"))
                    page = plain
                    braked = True
            if getattr(page, "template_used", False):
                term.type_out(t("styletpl.in_use",
                                domain=styletpl.domain_of(page.url)), delay=0.002)
            elif template and not braked and not page.low_text and styletpl.eligible(page):
                # A template exists for this domain but didn't grip this page
                # — say so instead of leaving the caller wondering why the
                # page looks plain. Not on thin pages (their own hint already
                # explains more) and not on pages without a document (Firecrawl
                # markdown) where the template never had a chance.
                term.error(t("styletpl.no_grip",
                             domain=styletpl.domain_of(page.url)))
            # JS-heavy page and Firecrawl in MCP mode? SysOp scrapes it afterward.
            thin = page.low_text
            # Firecrawl was on but didn't deliver (SDK mode, silent HTTP
            # fallback): show the reason instead of leaving the user in the dark.
            fc_error = getattr(page, "firecrawl_error", "")
            if fc_error:
                term.error(t("browser.firecrawl_failed", err=fc_error))
            if thin and self.sysop and self.firecrawl.get("enabled") and self.firecrawl.get("use_mcp"):
                md = self.sysop.scrape_markdown(url, self.firecrawl)
                if md:
                    page = page_from_markdown(md, url)
        except KeyboardInterrupt:
            # Ctrl+C while dialing/loading does NOT end the whole session,
            # it only aborts this dial attempt — back to the prompt.
            print(RESET)
            term.error(t("browser.dial_aborted"))
            return None
        return self._present(page, push_history, build_template=build_template)

    def _present(self, page, push_history=True, build_template=False):
        """Displays a finished page: style template, history, output.
        The shared tail end of dial() and the Firecrawl search."""
        page = self.ensure_template(page, force=build_template)
        if push_history and self.page:
            self.back_stack.append(self.page)
            self.forward_stack.clear()
        self.page = page
        self._find_word, self._find_pos = "", -1
        self.history.append({"url": page.url, "title": page.title})
        save_state(self.bookmarks, self.history)
        return self.show_page()

    def template_ready(self):
        """Can a template be learned at all? Needs an AI key — the rest is
        decided per page."""
        return bool(self.sysop and self.sysop.has_key())

    def ensure_template(self, page, force=False):
        """Learns the domain's style template if asked to (`x`) or if the
        automatic mode is on and the domain has none yet — and rebuilds the
        page with it. Without an AI key, on a non-HTML page or on a failed
        build the page is returned untouched."""
        from . import styletpl

        if not styletpl.eligible(page) or not self.template_ready():
            return page
        if not force and not (self.auto_template and not styletpl.exists(page.url)):
            return page

        result = self.sysop.build_template(page)
        if not result:
            self.term.error(t("styletpl.build_failed"))
            return page
        template, verified, total = result
        domain = styletpl.domain_of(page.url)
        styletpl.save(domain, self.sysop.model_name(), template, verified)
        self.term.type_out(
            t("styletpl.built", domain=domain, ok=verified, total=total), delay=0.003)
        return self.restyle(page) or page

    def restyle(self, page):
        """Rebuilds a page with its domain's template. Images come from the
        process buffer, so the second build costs no further fetches."""
        from . import styletpl
        from .page import build_page

        template = styletpl.load(page.url)
        if not template or not getattr(page, "html", ""):
            return None
        try:
            fresh = build_page(page.html, page.url, self.render_images,
                               self.img_width, self.img_mode, template,
                               js_rendered=getattr(page, "js_rendered", None))
        except Exception:
            return None
        # Everything not coming out of the blocks is taken from the original
        # page — title, logo and feed don't depend on the style.
        fresh.title = page.title
        fresh.logo_urls = page.logo_urls
        fresh.theme_color = page.theme_color
        fresh.feed_url = page.feed_url
        fresh.forms = page.forms
        return fresh

    def _template_line(self, page):
        """One line in the page's info box saying what the house template did
        here. Without it nobody can tell whether a domain HAS a template, let
        alone whether it gripped — the message on dialing scrolls away behind
        the page. Empty only where a template can never exist (gopher,
        gemini, internal screens)."""
        from . import styletpl

        domain = styletpl.domain_of(getattr(page, "url", ""))
        if not domain or not styletpl.eligible(page):
            return ""
        if not styletpl.exists(domain):
            return t("browser.template_none", domain=domain)
        if getattr(page, "template_used", False):
            return t("browser.template_used", domain=domain)
        return t("browser.template_idle", domain=domain)

    def show_page(self):
        term = self.term
        p = self.page
        domain = urlparse(p.url).netloc.removeprefix("www.")
        if self.color_auto:
            # Smart color mode: phosphor tone matching the page.
            _, term.color = pick_color(
                getattr(p, "theme_color", ""), urlparse(p.url).netloc
            )
        if self.header != "off":
            # The real logo carries the header only on the first visit to a
            # domain: as long as you stay on the same page, it remains the
            # random banner. Only a domain change brings the logo back.
            first_visit = domain != self._logo_domain
            art = (headers.logo_art(domain, getattr(p, "logo_urls", []), mode=self.img_mode)
                   if self.header == "logo" and first_visit else None)
            headers.show(term, domain, screen_width(), art)
            self._logo_domain = domain
        rows = [
            p.title,
            t("browser.page_links_info", url=p.url[:screen_width() - 20], count=len(p.links)),
        ]
        # Feed discovered in <head>? Offer the message base instead of hiding it.
        if getattr(p, "feed_url", ""):
            rows.append(t("browser.feed_available"))
        # Offer the page's search forms — otherwise nobody would find them.
        if getattr(p, "forms", []):
            rows.append(t("browser.forms_available", count=len(p.forms)))
        line = self._template_line(p)
        if line:
            rows.append(line)
        term.box(rows)
        pending = paginate(term, layout_page(p, term.color))
        term.rule()
        return pending  # possibly a command from the MORE prompt

    def search(self, query):
        # Firecrawl configured? Then use the real search API — DuckDuckGo's
        # HTML page now mostly blocks automated requests (bot block,
        # zero results). DDG remains the fallback without Firecrawl.
        fc = self.firecrawl or {}
        from .sysop import firecrawl_key
        key = firecrawl_key(fc)
        base = normalize_base_url(fc.get("base_url"))
        try:
            self.term.type_out("\n" + t("browser.searching", query=query), delay=0.02)
            page = None
            # Firecrawl already failed repeatedly? Then straight to DDG
            # instead of waiting for the same timeout again.
            if fc.get("enabled") and (key or base) and not firecrawl_muted():
                results, err = firecrawl_search(query, key, base)
                if results:
                    page = page_from_search_results(query, results)
                elif err:
                    self.term.error(t("browser.firecrawl_failed", err=err))
            if page is None:
                # Fallback without Firecrawl: DDG's HTML form, submitted via POST.
                page, err = ddg_search(query, self.render_images, self.img_width, self.img_mode)
                if err:
                    self.term.error(t("browser.no_carrier", err=err))
                    return None
        except KeyboardInterrupt:
            # Same as dialing: Ctrl+C only aborts the search, not the session.
            print(RESET)
            self.term.error(t("browser.dial_aborted"))
            return None
        return self._present(page)

    # -- Navigation -----------------------------------------------------

    def follow(self, num):
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return None
        url = self.page.link_url(num)
        if not url:
            self.term.error(t("browser.no_link", num=num, max=len(self.page.links)))
            return None
        return self.dial(url)

    def back(self):
        return self._history_step(self.back_stack, self.forward_stack,
                                  "browser.history_empty")

    def forward(self):
        return self._history_step(self.forward_stack, self.back_stack,
                                  "browser.no_forward_history")

    def _history_step(self, src, dst, empty_key):
        """Takes one step in history: current page onto `dst`, top
        of `src` shown."""
        if not src:
            self.term.error(t(empty_key))
            return None
        dst.append(self.page)
        self.page = src.pop()
        self._find_word, self._find_pos = "", -1
        return self.show_page()

    def reload(self):
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return None
        return self.dial(self.page.url, push_history=False)

    # -- Lists ---------------------------------------------------------

    def list_links(self, filter_word=""):
        """Dedicated link screen: 'l' shows all links, 'l <word>' filters
        by label/URL. Typing a number dials it directly."""
        term = self.term
        if not self.page or not self.page.links:
            term.error(t("browser.no_links_on_page"))
            return None
        needle = filter_word.strip().lower()
        hits = [
            (i, url, label)
            for i, (url, label) in enumerate(self.page.links, 1)
            if not needle or needle in label.lower() or needle in url.lower()
        ]
        if not hits:
            term.error(t("browser.no_matching_links", filter=filter_word, total=len(self.page.links)))
            return None
        header = t("browser.link_table_title", title=self.page.title[:screen_width() - 30])
        sub = t("browser.links_summary", hits=len(hits), total=len(self.page.links))
        if needle:
            sub += "  ·  " + t("browser.filter_label", filter=filter_word.strip())
        rows = [(str(i), label[:screen_width() - 40], url[:34]) for i, url, label in hits]
        choice = lightbar.menu(term, header, rows, subtitle=sub, page_size=15)
        return choice or None

    def show_history(self):
        term = self.term
        if not self.history:
            term.error(t("browser.history_empty"))
            return None
        from .nostalgia import recent_entries
        term.rule(t("browser.history_header"))
        for i, entry in enumerate(recent_entries(self.history, 20), 1):
            term.type_out(f"  [{i:>2}] {entry['title'][:screen_width() - 10]}", delay=0.001)
            print(term.color + DIM + f"       {entry['url'][:screen_width() - 8]}" + RESET)
        term.rule()
        return None

    def dial_recent(self, num):
        """'h <nr>': dial an entry from recent visits."""
        from .nostalgia import recent_entries
        recents = recent_entries(self.history, 20)
        if not 1 <= num <= len(recents):
            self.term.error(t("browser.no_history_entry", num=num))
            return None
        return self.dial(recents[num - 1]["url"])

    # -- Nodes ("Tabs") -------------------------------------------------

    def _store_node(self):
        self.nodes[self.node_idx] = {
            "page": self.page, "back": self.back_stack, "fwd": self.forward_stack,
        }

    def switch_node(self, num):
        if not 1 <= num <= MAX_NODES:
            self.term.error(t("browser.nodes_range", max=MAX_NODES))
            return None
        if num - 1 == self.node_idx:
            self.term.type_out(t("browser.already_on_node", num=num), delay=0.003)
            return None
        self._store_node()
        self.node_idx = num - 1
        node = self.nodes[self.node_idx] or {"page": None, "back": [], "fwd": []}
        self.page, self.back_stack, self.forward_stack = node["page"], node["back"], node["fwd"]
        self._find_word, self._find_pos = "", -1
        self.term.type_out(t("browser.node_on_line", num=num), delay=0.003)
        if self.page:
            return self.show_page()
        self.term.type_out(t("browser.empty_line_hint"), delay=0.002)
        return None

    def list_nodes(self):
        self._store_node()
        self.term.rule(t("browser.nodes_header"))
        for i, node in enumerate(self.nodes, 1):
            mark = "»" if i - 1 == self.node_idx else " "
            title = node["page"].title[:screen_width() - 12] if node and node["page"] else t("browser.node_free")
            self.term.type_out(f" {mark}[{i}] {title}", delay=0.001)
        self.term.rule()
        return None

    # -- In-page search --------------------------------------------

    def find_in_page(self, word):
        """'/word' jumps to the match, '/' alone to the next one."""
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return None
        word = word.strip()
        if word:
            self._find_word, self._find_pos = word, -1
        elif not self._find_word:
            self.term.error(t("browser.find_usage"))
            return None
        needle = self._find_word.lower()
        lines = layout_page(self.page, self.term.color)
        for i in range(self._find_pos + 1, len(lines)):
            if needle in ANSI_RE.sub("", lines[i][1]).lower():
                self._find_pos = i
                self.term.rule(t("browser.found_at", word=self._find_word, line=i + 1, total=len(lines)))
                return paginate(self.term, lines[i:])
        self._find_pos = -1
        self.term.error(t("browser.not_found", word=self._find_word))
        return None

    # -- Message Base (RSS/Atom) ----------------------------------------

    FEED_GUESSES = ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml")

    def show_feed(self, arg=""):
        """'rss' opens the page's feed (or guesses common paths),
        'rss <url>' opens any feed."""
        from .feeds import fetch_feed
        page, err = None, None
        if arg:
            feed_url = normalize_url(arg)
            self.term.type_out(t("browser.open_message_base", url=feed_url), delay=0.003)
            page, err = fetch_feed(feed_url)
        elif not self.page:
            self.term.error(t("browser.no_page_for_rss"))
            return None
        else:
            candidates = []
            if getattr(self.page, "feed_url", ""):
                candidates.append(self.page.feed_url)
            p = urlparse(self.page.url)
            candidates += [f"{p.scheme}://{p.netloc}{path}" for path in self.FEED_GUESSES]
            self.term.type_out(t("browser.search_message_base"), delay=0.003)
            for feed_url in candidates:
                page, err = fetch_feed(feed_url)
                if not err and page.links:
                    self.term.type_out(t("browser.feed_found", url=feed_url), delay=0.002)
                    break
            else:
                self.term.error(t("browser.no_feed_found"))
                return None
        if err:
            self.term.error(err)
            return None
        if self.page:
            self.back_stack.append(self.page)
            self.forward_stack.clear()
        self.page = page
        self._find_word, self._find_pos = "", -1
        return self.show_page()

    def show_bulletins(self, refresh=False):
        """'bu' opens the SysOp's bulletin board — the news from the
        configured source, each headline with its link to the article."""
        from . import bulletins
        if not bulletins.configured():
            self.term.error(t("bulletins.no_url"))
            return None
        # Stale bulletins are fetched again on their own — a feed goes hot
        # every few minutes, a page follows the configured cadence.
        if refresh or bulletins.stale():
            # A feed reads itself; only a plain page needs the SysOp.
            if bulletins.needs_ai() and not (self.sysop and self.sysop.has_key()):
                if not bulletins.items():
                    self.term.error(t("bulletins.no_key"))
                    return None
            else:
                self.term.type_out(t("bulletins.fetching"), delay=0.003)
                if not bulletins.refresh(self.sysop, force=refresh) and not bulletins.items():
                    self.term.error(t("bulletins.refresh_failed"))
                    return None
        # With a controllable terminal the board is a cursor menu; None means
        # there is no such terminal, so the classic [n] page takes over.
        chosen = self._bulletin_menu()
        if chosen is not None:
            return self.dial(chosen) if chosen else None
        if self.page:
            self.back_stack.append(self.page)
            self.forward_stack.clear()
        self.page = bulletins.page()
        self._find_word, self._find_pos = "", -1
        return self.show_page()

    def _bulletin_menu(self):
        """The bulletin board as a cursor menu: up/down picks a bulletin,
        ENTER dials the article behind it, ESC goes back.

        Returns the chosen URL, '' for back — or None when the terminal
        can't be driven, in which case the caller falls back to the page."""
        import shutil

        from . import bulletins, keys
        if not keys.available():
            return None
        rows, urls = bulletins.board_rows()
        if not rows:
            return None
        # Menu box (4), footer (2) and the "more" line leave the rest to the list.
        view = max(3, shutil.get_terminal_size((80, 24)).lines - 8)
        start = 0
        while True:
            key = lightbar.menu(self.term, t("bulletins.page_title"), rows,
                                subtitle=bulletins.board_subtitle(),
                                hint=t("bulletins.menu_hint"),
                                page_size=view, start=start)
            if not key:
                return ""
            if key in urls:
                return urls[key]
            # A bulletin the source gave us without a link: say so and stay.
            self.term.beep()
            start = lightbar.index_of(rows, key)

    def show_weather(self, refresh=False):
        """'we' opens the weather station — current sky, three more days
        and the SysOp's row of world clocks. Without a configured place
        only the clocks are left, which is still a useful page."""
        from . import weather
        if weather.configured() and (refresh or weather.stale()):
            self.term.type_out(t("weather.fetching"), delay=0.003)
            if not weather.refresh(force=refresh):
                self.term.error(t("weather.refresh_failed"))
        if self.page:
            self.back_stack.append(self.page)
            self.forward_stack.clear()
        self.page = weather.page()
        self._find_word, self._find_pos = "", -1
        return self.show_page()

    # -- Forms (GET) ------------------------------------------------

    def forms_menu(self, arg=""):
        """'fm' opens the page's input mask, 'fm <nr>' a specific one.
        GET forms only — those are ultimately just addresses with parameters."""
        from . import forms as formlib
        term = self.term
        masks = getattr(self.page, "forms", []) if self.page else []
        if not masks:
            term.error(t("browser.no_forms"))
            return None
        if arg.strip().isdigit():
            num = int(arg.strip())
            if not 1 <= num <= len(masks):
                term.error(t("browser.no_form_num", num=num, max=len(masks)))
                return None
            return self.fill_form(masks[num - 1])
        if len(masks) == 1:
            return self.fill_form(masks[0])
        rows = [
            (str(i), formlib.form_title(m, i)[:screen_width() - 40],
             t("browser.form_field_count", count=len(formlib.visible_fields(m))))
            for i, m in enumerate(masks, 1)
        ]
        choice = lightbar.menu(term, t("browser.forms_header"), rows, page_size=10)
        if not choice or not choice.isdigit():
            return None
        num = int(choice)
        if not 1 <= num <= len(masks):
            return None
        return self.fill_form(masks[num - 1])

    def fill_form(self, mask):
        """Ask field by field and dial the finished address.
        Empty input takes over the default value, an empty required field
        stays empty — exactly as in a real form."""
        from . import forms as formlib
        term = self.term
        fields = formlib.visible_fields(mask)
        term.rule(t("browser.form_header", title=formlib.form_title(mask, 1)))
        values = {}
        for field in fields:
            if field["kind"] == "select":
                values[field["name"]] = self._ask_select(field)
            else:
                label = field["label"]
                if field["value"]:
                    label = t("browser.form_field_default", label=label, value=field["value"])
                answer = term.prompt(f"  {label}: ")
                values[field["name"]] = answer if answer else field["value"]
        term.rule()
        url = formlib.submit_url(mask, values)
        return self.dial(url)

    def _ask_select(self, field):
        """Selection list: a number selects, text searches the label, empty
        takes the default value."""
        term = self.term
        options = field["options"]
        term.type_out(f"  {field['label']}:", delay=0.002)
        for i, (_, label) in enumerate(options, 1):
            term.type_out(f"    [{i:>2}] {label}", delay=0.001)
        answer = (term.prompt(t("browser.form_select_prompt")) or "").strip()
        if not answer:
            return field["value"]
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        needle = answer.lower()
        for value, label in options:
            if needle in label.lower():
                return value
        return answer   # freely typed — let the server decide

    # -- ZMODEM download ------------------------------------------------

    def download(self, arg):
        """'dl' saves the current page as text, 'dl <nr>' the link target."""
        from .nostalgia import safe_filename, zmodem_download
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return
        if arg.isdigit():
            url = self.page.link_url(int(arg))
            if not url:
                self.term.error(t("browser.no_link_num", num=arg))
                return
            try:
                import requests
                resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                self.term.error(t("browser.download_failed", error=e))
                return
            name = urlparse(url).path.rsplit("/", 1)[-1] or self.page.links[int(arg) - 1][1]
            ext = "" if "." in name else ".html"
            zmodem_download(self.term, safe_filename(name, ext or ".html"), resp.content)
            return
        text = f"{self.page.title}\n{self.page.url}\n\n" + page_text(self.page)
        zmodem_download(self.term, safe_filename(self.page.title), text.encode("utf-8"))

    # -- Real browser ---------------------------------------------------

    def open_external(self, arg=""):
        """'o' opens the current page in the system browser, 'o <nr>' a link."""
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return
        if arg.isdigit():
            url = self.page.link_url(int(arg))
            if not url:
                self.term.error(t("browser.no_link_num", num=arg))
                return
        else:
            url = self.page.url
        if not url or not url.startswith(("http://", "https://")):
            self.term.error(t("browser.no_external_url"))
            return
        if open_in_system_browser(url):
            self.term.type_out(t("browser.opened_external", url=url), delay=0.003)
        else:
            self.term.error(t("browser.open_external_failed", url=url))

    # -- Bookmarks ------------------------------------------------------

    def dial_bookmark(self, num):
        """Speed dial: 'd <nr>' dials bookmark no. <nr>."""
        if not 1 <= num <= len(self.bookmarks):
            self.term.error(t("browser.no_bookmark", num=num))
            return None
        return self.dial(self.bookmarks[num - 1]["url"])

    def add_bookmark(self):
        if not self.page:
            self.term.error(t("browser.no_page_loaded"))
            return
        if any(b["url"] == self.page.url for b in self.bookmarks):
            self.term.type_out(t("browser.already_bookmarked"), delay=0.003)
            return
        self.bookmarks.append({"url": self.page.url, "title": self.page.title})
        save_state(self.bookmarks, self.history)
        self.term.type_out(t("browser.bookmarked", title=self.page.title[:screen_width() - 14]), delay=0.003)

    def bookmark_menu(self):
        term = self.term
        if not self.bookmarks:
            term.rule(t("browser.bookmarks_header"))
            term.type_out(t("browser.no_bookmarks"), delay=0.002)
            term.rule()
            return None

        def rows():
            return [(str(i), b["title"][:screen_width() - 40], b["url"][:34])
                    for i, b in enumerate(self.bookmarks, 1)]

        def on_key(pressed, key):
            """'x' or DEL deletes the marked bookmark."""
            if pressed not in ("x", "X", "d", "D"):
                return False
            self.bookmarks.pop(int(key) - 1)
            save_state(self.bookmarks, self.history)
            return True

        choice = lightbar.menu(term, t("browser.bookmarks_header"), rows, on_key=on_key,
                               page_size=15, hint=t("browser.bookmark_hint"))
        if not choice:
            return None
        try:
            return self.dial(self.bookmarks[int(choice) - 1]["url"])
        except (ValueError, IndexError):
            term.error(t("browser.invalid_input"))
            return None
