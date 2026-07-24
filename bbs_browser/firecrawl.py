"""Firecrawl client: scrape/search via the SDK, config check, circuit breaker."""

import requests

from .i18n import t

FIRECRAWL_CLOUD = "https://api.firecrawl.dev"


def firecrawl_api_key(cfg):
    """The usable Firecrawl key. cfg['api_key'] can be a keyring marker
    instead of the key itself — reading it raw would send the marker as the
    token and every call would look like an invalid key. Imported late
    because sysop pulls this module back in."""
    from .sysop import firecrawl_key
    return firecrawl_key(cfg or {})


def firecrawl_check(cfg, ai_key=""):
    """Check Firecrawl configuration. In cloud without a scrape (and
    thus without credits) — just key and credit balance. For self-hosting,
    no credits run, so a real test scrape is done there, checking exactly the
    path the browser takes later (v2 with v1 fallback). Returns
    a list (status, message); status is "OK", "WARN" or "ERROR"."""
    from .fetch import normalize_base_url
    cfg = cfg or {}
    results = []
    api_key = firecrawl_api_key(cfg)
    base = normalize_base_url(cfg.get("base_url"))
    use_mcp = bool(cfg.get("use_mcp"))
    self_hosted = bool(base)

    results.append(("OK" if cfg.get("enabled") else "WARN",
                    t("page.firecrawl_enabled") if cfg.get("enabled")
                    else t("page.firecrawl_disabled")))
    mode_str = t("page.mode_mcp") if use_mcp else t("page.mode_sdk")
    results.append(("OK", t("page.mode_label", mode=mode_str)))

    if use_mcp:
        # MCP: the SysOp needs a direct Anthropic key, not a gateway.
        if not ai_key:
            results.append(("FEHLER", t("page.fc_error_no_ai_key")))
        elif ai_key.startswith("vck_"):
            results.append(("FEHLER", t("page.fc_error_vck_key")))
        else:
            results.append(("OK", t("page.fc_ok_ai_key")))
        if not self_hosted and not api_key:
            results.append(("FEHLER", t("page.fc_error_no_fc_key")))
        elif api_key:
            results.append(("OK", t("page.fc_ok_key_set")))
    else:
        try:
            import firecrawl  # noqa: F401
            results.append(("OK", t("page.fc_ok_sdk_installed")))
        except ImportError:
            results.append(("FEHLER", t("page.fc_error_sdk_missing")))
        if not api_key:
            msg = t("page.fc_warn_no_key_self_hosted") if self_hosted else t("page.fc_error_no_key_cloud")
            level = "WARN" if self_hosted else "FEHLER"
            results.append((level, msg))

    # Reachability / key validity — without scrape, costs nothing.
    if self_hosted:
        probe = base if use_mcp else base + "/test"
        try:
            requests.get(probe, timeout=8)
            results.append(("OK", t("page.fc_ok_host_reachable", base=base)))
        except Exception as e:
            results.append(("FEHLER", t("page.fc_error_host_unreachable", base=base, error=str(e))))
        # The host can respond and the scrape API can still be missing (e.g., an
        # older instance without /v2). For self-hosting, a test scrape costs
        # no credits — so check the real path straight away instead of
        # reporting "OK" and letting the user run into it on first call.
        if not use_mcp:
            _, _, _, err = firecrawl_scrape("https://example.com", api_key, base)
            if err:
                results.append(("FEHLER", t("page.fc_scrape_probe_fail", error=err)))
            else:
                results.append(("OK", t("page.fc_scrape_probe_ok")))
    elif api_key and not use_mcp:
        try:
            resp = requests.get(
                FIRECRAWL_CLOUD + "/v1/team/credit-usage",
                headers={"Authorization": f"Bearer {api_key}"}, timeout=8,
            )
            if resp.status_code == 200:
                remaining = resp.json().get("data", {}).get("remaining_credits")
                extra = t("page.fc_extra_credits", remaining=remaining) if remaining is not None else ""
                results.append(("OK", t("page.fc_ok_cloud_valid") + extra))
            elif resp.status_code in (401, 403):
                results.append(("FEHLER", t("page.fc_error_invalid_key")))
            else:
                results.append(("WARN", t("page.fc_warn_http_status", status=resp.status_code)))
        except Exception as e:
            results.append(("FEHLER", t("page.fc_error_cloud_unreachable", error=str(e))))

    return results


def _firecrawl_doc_fields(doc):
    """Pull the three formats from an SDK response — v1 and v2 name the
    raw HTML differently (rawHtml vs. raw_html)."""
    return (
        getattr(doc, "html", None) or "",
        getattr(doc, "markdown", None) or "",
        getattr(doc, "raw_html", None) or getattr(doc, "rawHtml", None) or "",
    )


# Wait time after loading before Firecrawl collects the DOM. Without waitFor,
# Firecrawl uses the bare fetch engine for many pages (no JS!) or
# captures the DOM before an SPA has injected its content — then only the
# empty shell comes back. With waitFor > 0, the browser engine is
# forced and the page JS gets time to run. The cost: every page
# waits this span, even static ones — so chosen moderately.
FIRECRAWL_WAIT_MS = 3000

# Circuit breaker: if Firecrawl doesn't work (host down, wrong key, credits
# used up), EVERY page load would otherwise run into its timeout first and
# print the same error again. After this many consecutive failures Firecrawl
# is ignored for the rest of the session and the normal path (JS render /
# plain HTTP) takes over. A successful call — or a config change — clears it.
FIRECRAWL_MAX_FAILURES = 2
_fc_failures = 0


def firecrawl_muted():
    """True as soon as Firecrawl has failed too often — callers then skip it."""
    return _fc_failures >= FIRECRAWL_MAX_FAILURES


def firecrawl_reset():
    """Give Firecrawl a fresh chance — after a config change or a check run."""
    global _fc_failures
    _fc_failures = 0


def _fc_ok():
    global _fc_failures
    _fc_failures = 0


def _fc_failed():
    global _fc_failures
    _fc_failures += 1


def firecrawl_scrape(url, api_key, base):
    """Scrape a URL via the Firecrawl SDK and return
    (html, markdown, raw_html, error). Tries v2 API first; if it fails
    (e.g. because an older self-hosted instance only knows /v1), silently
    falls back to v1 API. Only if BOTH fail does the error come back —
    so the browser can show it instead of silently swallowing it."""
    kwargs = {"api_key": api_key or "fc-self-hosted"}
    if base:
        kwargs["api_url"] = base
    formats = ["markdown", "html", "rawHtml"]
    try:
        from firecrawl import Firecrawl
        doc = Firecrawl(**kwargs).scrape(url, formats=formats, wait_for=FIRECRAWL_WAIT_MS)
        return (*_firecrawl_doc_fields(doc), None)
    except Exception as e:
        first_error = e
    # v2 failed — older self-hosting instances only speak v1 API.
    try:
        from firecrawl import V1FirecrawlApp
        doc = V1FirecrawlApp(**kwargs).scrape_url(url, formats=formats, wait_for=FIRECRAWL_WAIT_MS)
        return (*_firecrawl_doc_fields(doc), None)
    except Exception:
        # The v2 error is more informative (v1 is just the fallback).
        return "", "", "", str(first_error) or type(first_error).__name__


def _search_result_fields(item):
    """url/title/description of a search hit — SDK object or dict."""
    if isinstance(item, dict):
        get = item.get
    else:
        def get(k, default=""):
            return getattr(item, k, default)
    return get("url") or "", get("title") or "", get("description") or ""


def _search_results(data):
    """Pull web hits from an SDK search response — v2 names the list
    'web', v1 'data'; entries can be objects or dicts."""
    if isinstance(data, dict):
        items = data.get("web") or data.get("data") or []
    else:
        items = getattr(data, "web", None) or getattr(data, "data", None) or []
    out = []
    for item in items or []:
        url, title, desc = _search_result_fields(item)
        if url:
            out.append((url, title or url, desc))
    return out


def firecrawl_search(query, api_key, base, limit=8):
    """Search via Firecrawl search API and return ([(url, title, snippet)],
    error). Tries v2 API first, silently falls back to v1 — like
    firecrawl_scrape. This replaces the DDG HTML scrape, which DuckDuckGo
    now mostly blocks for automated requests (bot block, zero results)."""
    kwargs = {"api_key": api_key or "fc-self-hosted"}
    if base:
        kwargs["api_url"] = base
    try:
        from firecrawl import Firecrawl
        data = Firecrawl(**kwargs).search(query, limit=limit)
        _fc_ok()
        return _search_results(data), None
    except Exception as e:
        first_error = e
    try:
        from firecrawl import V1FirecrawlApp
        data = V1FirecrawlApp(**kwargs).search(query)
        _fc_ok()
        return _search_results(data), None
    except Exception:
        # The v2 error is more informative (v1 is just the fallback).
        _fc_failed()
        return [], str(first_error) or type(first_error).__name__
