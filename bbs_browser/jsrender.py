"""JS rendering via Playwright — the replacement for a bare requests fetch.

The modern web often assembles content only in the browser; a plain HTTP GET
then delivers an empty shell. Playwright launches a real Chromium, lets the
JS run, and hands us the finished DOM.

Optional: if the package or the Chromium binary is missing, available()
simply reports False and fetch_page falls back to requests. The browser is
started once and kept open until the program exits — a cold start per page
would be noticeable on every connection.
"""

import atexit
import os

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_state = {"checked": False, "ok": False, "pw": None, "browser": None}


def _disabled():
    return os.environ.get("BBS_NO_JS", "").strip().lower() in ("1", "true", "yes")


def available():
    """True if Playwright can be imported and a Chromium is available."""
    if _disabled():
        return False
    if not _state["checked"]:
        _state["checked"] = True
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
            _state["ok"] = True
        except Exception:
            _state["ok"] = False
    return _state["ok"]


def _browser():
    """Running Chromium — started on first call, then reused."""
    if _state["browser"] is not None:
        return _state["browser"]
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    _state["pw"] = pw
    _state["browser"] = browser
    atexit.register(shutdown)
    return browser


def shutdown():
    """Shut down Chromium and the Playwright driver (idempotent)."""
    for key in ("browser", "pw"):
        obj = _state.get(key)
        _state[key] = None
        if obj is None:
            continue
        try:
            obj.close() if key == "browser" else obj.stop()
        except Exception:
            pass


def _wait_for_content(page, min_chars=800, max_wait_ms=10000, poll_ms=500):
    """Wait for the actual content, not just for 'load'.

    SPAs (Instagram & co.) fire 'load' before React/Vue attaches the content
    to the DOM — the body text is then still essentially empty. So: poll
    until the visible text reaches a minimum length OR two consecutive
    measurements are stable (classic pages are ready immediately and thus
    only cost a single poll). Hard cap so that endless streamers don't hold
    us up.
    """
    waited = 0
    last = -1
    while waited < max_wait_ms:
        try:
            length = page.evaluate("() => document.body ? document.body.innerText.length : 0")
        except Exception:
            return
        # Stable at 0 characters only counts as "really empty" after 2s —
        # right after 'load', 0 is the normal case before the JS even runs.
        if length >= min_chars or (length == last and (length > 0 or waited >= 2000)):
            return
        last = length
        page.wait_for_timeout(poll_ms)
        waited += poll_ms


# ONLY decline — this used to also have "Accept all" as a stopgap, and that
# made the browser consent to tracking on the caller's behalf just to get rid
# of a banner. If no decline button is found, the banner is instead thrown
# out of the DOM (_strip_consent). The patterns cover the common CMPs (Meta,
# OneTrust, Cookiebot, Usercentrics) in German and English.
_REJECT_PATTERNS = [
    "Decline optional cookies", "Only allow essential cookies",
    "Reject all", "Reject All", "Reject all cookies",
    "Necessary cookies only", "Essential cookies only", "Continue without accepting",
    "Optionale Cookies ablehnen", "Nur erforderliche Cookies erlauben",
    "Alle ablehnen", "Alle Cookies ablehnen", "Nur notwendige Cookies",
    "Nur essenzielle Cookies", "Ohne Einwilligung fortfahren", "Ablehnen",
]


def _dismiss_consent(page):
    """Get rid of the cookie banner — decline first, then clean up.

    Two steps, because each has its own gaps on its own: clicking Decline is
    the clean way and lets pages that only load their content AFTER a
    decision keep working. But it doesn't hit anywhere near every one of the
    countless banner designs. The subsequent DOM removal instead matches by
    selector and needs no button. Both are best effort: no match, no drama."""
    for label in _REJECT_PATTERNS:
        try:
            btn = page.get_by_role("button", name=label, exact=True).first
            if btn.count() and btn.is_visible():
                btn.click(timeout=2000)
                page.wait_for_timeout(1000)
                break
        except Exception:
            continue
    _strip_consent(page)


def _strip_consent(page):
    """Remove leftover consent containers from the DOM and release the
    scroll lock the modals impose on <body>."""
    from .constants import CONSENT_SELECTORS

    try:
        page.evaluate(
            """(selectors) => {
                for (const sel of selectors) {
                    let nodes;
                    try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
                    nodes.forEach(n => n.remove());
                }
                for (const el of [document.documentElement, document.body]) {
                    if (el) { el.style.overflow = ''; el.style.position = ''; }
                }
            }""",
            list(CONSENT_SELECTORS),
        )
    except Exception:
        pass


def render(url, timeout=20000):
    """(html, final_url) after JS has run, or (None, None) on error.

    The Chromium binary is often missing even though the pip package is
    present ('playwright install chromium' forgotten) — the startup then
    fails here and we mark JS rendering as off for the rest of the session,
    so that not every page runs into the same timeout again.
    """
    if not available():
        return None, None
    try:
        browser = _browser()
    except Exception:
        _state["ok"] = False
        return None, None

    context = None
    try:
        context = browser.new_context(user_agent=_USER_AGENT, java_script_enabled=True)
        page = context.new_page()
        # 'domcontentloaded' instead of 'networkidle': pages with continuous
        # polling (analytics, websockets) never go idle and would otherwise
        # run into the timeout even though the content has long been ready.
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        try:
            page.wait_for_load_state("load", timeout=5000)
        except Exception:
            pass
        _wait_for_content(page)
        _dismiss_consent(page)
        return page.content(), page.url
    except Exception:
        return None, None
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
