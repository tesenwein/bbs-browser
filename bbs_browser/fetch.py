"""Network fetch and DDG search: URLs in, parsed pages out."""

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .constants import USER_AGENT
from . import firecrawl
from .i18n import t
from .page import Page, build_page, find_logos, page_from_markdown


def normalize_url(url, default_scheme="https"):
    """Single rule for addresses throughout the browser: spaces gone,
    missing scheme added. gopher:// and gemini:// stay untouched."""
    url = (url or "").strip()
    if url and "://" not in url:
        url = f"{default_scheme}://{url}"
    return url


def normalize_base_url(base):
    """Like normalize_url, but for host entries (without trailing slash)."""
    return normalize_url(base).rstrip("/")


DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"


def ddg_url(query):
    """The search as a selectable address — so it stays usable
    in history and bookmarks even though it's queried via POST."""
    from urllib.parse import quote_plus
    return DDG_HTML_ENDPOINT + "?q=" + quote_plus(query)


def ddg_search(query, render_images=False, img_width=60, img_mode="blocks"):
    """Query DuckDuckGo's HTML endpoint — via POST.

    The GET path (…/html/?q=…) has been running into bot blocks for some time: DDG
    responds with 202 and a challenge page instead of results, and JS rendering
    only sees an error message. The same form submitted via POST still delivers
    the normal result list — it's also the path the page's submit button takes.
    """
    try:
        resp = requests.post(
            DDG_HTML_ENDPOINT,
            data={"q": query, "b": ""},
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": DDG_HTML_ENDPOINT,
                "Origin": "https://html.duckduckgo.com",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        return None, t("page.error_fetch_failed", error=str(e))
    page = build_page(resp.text, ddg_url(query), render_images, img_width, img_mode)
    page.is_search = True
    if not page.links:
        # Distinguish bot block (202/challenge page) from honest empty
        # result list — the message must not lie.
        if resp.status_code == 202 or "anomaly" in resp.text[:4000].lower():
            return None, t("page.error_ddg_blocked")
        return None, t("page.error_ddg_no_results", query=query)
    return page, None


def page_from_search_results(query, results):
    """Build a BBS page with numbered links from Firecrawl search results.
    The page carries the DDG search as URL — so the entry stays
    selectable in history even if Firecrawl is later unconfigured."""
    from urllib.parse import quote_plus
    page = Page(
        "https://html.duckduckgo.com/html/?q=" + quote_plus(query),
        t("page.search_results_title", query=query),
    )
    page.blocks.append({"type": "heading", "content": t("page.search_results_title", query=query)})
    page.is_search = True
    for url, title, desc in results:
        num = page.add_link(url, title)
        marker = f" [{num}]" if num else ""
        page.blocks.append({"type": "text", "content": f"{title}{marker}"})
        if desc:
            page.blocks.append({"type": "text", "content": desc})
    return page


def fetch_source(url, firecrawl_cfg=None):
    """The raw document of a URL over the BEST available line, in the same
    order fetch_page uses: Firecrawl (raw HTML, the JS-rendered document),
    then a real Chromium via Playwright, then a bare HTTP fetch. Returns
    (html, final_url) — ("", "") if nothing came through.

    Selectors are learned against this document, so a template must see the
    same page the browser will later set from. A verification page fetched
    over a thinner line than the real one would teach selectors for a
    document that never reaches the screen."""
    if urlparse(url).scheme not in ("http", "https"):
        return "", ""

    cfg = firecrawl_cfg or {}
    api_key = firecrawl.firecrawl_api_key(cfg)
    base = normalize_base_url(cfg.get("base_url"))
    if (cfg.get("enabled") and not cfg.get("use_mcp") and (api_key or base)
            and not firecrawl.firecrawl_muted()):
        # Firecrawl's MCP mode only ever yields markdown — no document to
        # hang selectors on, so it is skipped here just like in fetch_page.
        html, _md, raw, _err = firecrawl.firecrawl_scrape(url, api_key, base)
        source = raw or html
        if source:
            return source, url
    else:
        from . import jsrender
        if jsrender.available():
            html, final_url = jsrender.render(url)
            if html:
                return html, final_url or url

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return "", ""
    if "html" not in resp.headers.get("Content-Type", "text/html").lower():
        return "", ""
    if "charset" not in resp.headers.get("Content-Type", "").lower():
        resp.encoding = resp.apparent_encoding
    return resp.text, resp.url


def fetch_page(url, firecrawl_cfg=None, render_images=True, img_width=60,
               img_mode="blocks", template=None):
    """firecrawl_cfg: {"enabled": bool, "api_key": str, "base_url": str} — base_url
    allows self-hosted Firecrawl instances. On errors the browser falls back
    to normal HTTP; the Firecrawl error is attached to the page (page.firecrawl_error)
    so the browser can report it."""
    scheme = urlparse(url).scheme
    if scheme == "gopher":
        from .retronet import fetch_gopher
        return fetch_gopher(url)
    if scheme == "gemini":
        from .retronet import fetch_gemini
        return fetch_gemini(url)

    cfg = firecrawl_cfg or {}
    api_key = firecrawl.firecrawl_api_key(cfg)
    base = normalize_base_url(cfg.get("base_url"))
    fc_error = None
    # Firecrawl already failed repeatedly this session? Then don't wait for
    # its timeout again on every page — treat it as switched off.
    fc_active = bool(cfg.get("enabled")) and not firecrawl.firecrawl_muted()
    # Split "enabled" into what Firecrawl can ACTUALLY do here. Enabled alone
    # is not a renderer: a Firecrawl toggled on but never given a key (and no
    # self-hosted host) can't scrape a thing. Self-hosting often runs without a
    # key — then the host is enough. MCP mode yields only markdown and is
    # served later by the SysOp (see browser.dial), not here.
    fc_sdk = fc_active and not cfg.get("use_mcp") and (api_key or base)
    fc_mcp = fc_active and bool(cfg.get("use_mcp"))
    if fc_sdk:
        html, md, raw, fc_error = firecrawl.firecrawl_scrape(url, api_key, base)
        # Book the outcome for the circuit breaker: an empty response without
        # an error is a malfunction too, otherwise it would never trip.
        if raw or html or md:
            firecrawl._fc_ok()
        else:
            firecrawl._fc_failed()
        # The RAW HTML is the complete (JS-rendered) document:
        # <head> icons, the <header> with logo and the whole page structure
        # are only there. Firecrawl's "html" format is cleaned and throws away
        # exactly this page header — then logo AND structure are missing. build_page
        # cleans itself (scripts, header/nav/footer, reader mode, logo search) and
        # gets the same raw page as normal HTTP fetch; so raw HTML first,
        # the cleaned one only as fallback.
        source_html = raw or html
        if source_html:
            try:
                page = build_page(source_html, url, render_images, img_width, img_mode, template, js_rendered=True)
                # JS apps (Instagram & Co.): the HTML parses thin even though
                # Firecrawl delivers usable markdown — then prefer that.
                if not (page.low_text and md):
                    return page, None
            except Exception:
                pass  # HTML unparseable — Markdown is still there
        if md:
            page = page_from_markdown(md, url)
            # The logo hangs in the page header of the raw HTML — can't get it
            # from the markdown alone.
            page.logo_urls = find_logos(BeautifulSoup(raw, "html.parser"), url) if raw else []
            return page, None
        # Neither HTML nor Markdown, but also no error? Then an empty
        # response came back — that's also a reason to tell the user.
        if not fc_error:
            fc_error = t("page.fc_error_empty_scrape")
        if firecrawl.firecrawl_muted():
            fc_error += " — " + t("page.fc_error_muted")

    # Between Firecrawl and bare HTTP fetch: a real Chromium that
    # executes the page JS. If Playwright isn't installed, it's a
    # no-op and we continue with requests as before. Playwright steps in
    # whenever Firecrawl will NOT render this page itself — Firecrawl off, or
    # on but with no way to scrape (no key/host) and not in MCP mode. When
    # Firecrawl DOES render (the SDK scrape above, or MCP via the SysOp),
    # Playwright stays out: a second Chromium behind its back would silently
    # swap results on every Firecrawl failure, and the user would see a
    # Playwright page thinking it was Firecrawl's work.
    from . import jsrender
    if not fc_sdk and not fc_mcp and jsrender.available():
        html, final_url = jsrender.render(url)
        if html:
            try:
                page = build_page(html, final_url or url, render_images, img_width, img_mode, template, js_rendered=True)
                return page, None
            except Exception:
                pass  # unparseable — the HTTP path below is still there

    current = url
    for hop in range(3):
        try:
            resp = requests.get(current, headers={"User-Agent": USER_AGENT}, timeout=15, allow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            return None, t("page.error_fetch_failed", error=str(e))
        # Without charset in header, requests guesses ISO-8859-1 — umlaut salad on
        # older pages. Better to determine encoding from content.
        if "charset" not in resp.headers.get("Content-Type", "").lower():
            resp.encoding = resp.apparent_encoding
        page = build_page(resp.text, resp.url, render_images, img_width, img_mode, template, js_rendered=False)
        # Meta-refresh (popular on old pages) treat like a redirect.
        if page.refresh_url and page.refresh_url != resp.url and hop < 2:
            current = page.refresh_url
            continue
        # Firecrawl was on but didn't deliver: attach the reason to the page
        # so the browser doesn't silently swallow it.
        if fc_error:
            page.firecrawl_error = fc_error
        return page, None
