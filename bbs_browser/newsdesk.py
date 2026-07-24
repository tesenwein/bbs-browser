"""The bulletin board's news sources — and the layer that makes them comparable.

A caller may wire up as many sources as they like, and they come in two very
different kinds:

* an **RSS/Atom feed** — already exactly what a bulletin is: one clean,
  dated headline per entry. Free, fast, no AI involved.
* a **plain news page** — a link soup the SysOp has to read and rewrite in
  board tone. Costs a key, and carries no usable date at all.

Mixing those two shapes is what this module is for. Every source, whatever
its kind, is funnelled through :func:`fetch` into ONE entry shape::

    {"text", "title", "url", "ts", "source", "kind"}

    text   — the bulletin line as it appears on the board
    title  — the original headline (identical to `text` for a feed)
    url    — the article behind it ("" when the source gave none)
    ts     — publication date in epoch seconds, or None if unknown
    source — short label of the origin, e.g. "srf.ch"
    kind   — "rss" or "ai", so the board can explain where a line came from

Only once everything wears that shape does :func:`merge` put the entries in
order: newest first, duplicates dropped. Undated entries (i.e. everything
the AI dug out of a page) cannot join the timeline honestly, so they land
after the dated ones instead of being stamped with the fetch time — a made-up
date would silently outrank real ones.
"""

from urllib.parse import urlparse

from .i18n import t

MAX_SOURCE = 30        # headlines handed to the AI, per source
MAX_TEXT = 150         # a bulletin is one line, not an article
MIN_HEADLINE = 25      # shorter link texts on a page are navigation, not news

RSS, AI = "rss", "ai"


# -- Source list -----------------------------------------------------------


def normalize(raw):
    """The configured sources as a clean list of {"url", "enabled"}.

    Accepts what older versions stored (a single "url" string) as well as
    the list form, so an existing setup keeps working untouched."""
    if isinstance(raw, str):
        raw = [raw] if raw.strip() else []
    out, seen = [], set()
    for item in raw or []:
        url = (item if isinstance(item, str) else item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        enabled = True if isinstance(item, str) else bool(item.get("enabled", True))
        out.append({"url": url, "enabled": enabled})
    return out


def enabled_urls(sources):
    return [s["url"] for s in normalize(sources) if s["enabled"]]


def label_for(url):
    """The origin as a dateline: the bare host. Feed titles are long and
    full of marketing ("Home - all news, analyses | ..."), so the domain is
    the honest short form — and it is what tells two mixed sources apart."""
    host = urlparse(url).netloc.removeprefix("www.")
    return host or url[:32]


# -- Fetching: every kind of source, one entry shape -----------------------


def _page_of(url):
    """(page, is_feed) for a source URL — or (None, False) if unreachable.

    A URL is tried as a feed first, because that is the cheap path. Only if
    that fails is it fetched as a page, and even then a feed advertised in
    its <head> still wins: it costs no key."""
    from .feeds import fetch_feed
    from .fetch import fetch_page, normalize_url
    from .state import load_section

    url = normalize_url(url)
    page, err = fetch_feed(url)
    if not err and page and page.feed_items:
        return page, True
    page, err = fetch_page(url, load_section("firecrawl"), render_images=False)
    if err or not page:
        return None, False
    if page.feed_url:
        found, feed_err = fetch_feed(page.feed_url)
        if not feed_err and found and found.feed_items:
            return found, True
    return page, False


def _from_feed(page, source, count):
    """Feed entries as bulletins, one to one — no AI, no cost."""
    entries = []
    for item in page.feed_items:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        entries.append({"text": title[:MAX_TEXT], "title": title,
                        "url": item.get("url", ""), "ts": item.get("ts"),
                        "source": source, "kind": RSS})
    return entries[:count]


def _parse_ai(text, heads, source):
    """The AI answers one bulletin per line as '<nr>|<text>'. Anything that
    doesn't fit that shape is dropped instead of ending up on the board."""
    out = []
    for line in (text or "").splitlines():
        num, sep, body = line.partition("|")
        if not sep:
            continue
        num = num.strip().lstrip("[").rstrip("]").strip()
        body = " ".join(body.split())[:MAX_TEXT]
        if not num.isdigit() or not body:
            continue
        idx = int(num) - 1
        if not 0 <= idx < len(heads):
            continue
        title, link = heads[idx]
        # No date: a page says nothing about when it published what.
        out.append({"text": body, "title": title, "url": link,
                    "ts": None, "source": source, "kind": AI})
    return out


def _from_page(page, source, count, sysop):
    """A news page through the SysOp: headlines out of the link soup,
    rewritten in board tone. Without a key there is nothing to be had."""
    if not sysop or not sysop.has_key():
        return []
    heads = [(label.strip(), target) for target, label in page.links
             if len(label.strip()) >= MIN_HEADLINE][:MAX_SOURCE]
    if not heads:
        return []
    listing = "\n".join(f"{i}. {title}" for i, (title, _) in enumerate(heads, 1))
    try:
        answer = sysop._raw_complete(
            t("bulletins.prompt_system", count=count, chars=MAX_TEXT),
            [{"role": "user", "content": t("bulletins.prompt_user",
                                           source=page.title or source,
                                           count=count, headlines=listing)}],
            max_tokens=700,
        )
    except Exception:
        return []
    return _parse_ai(answer, heads, source)[:count]


def fetch(url, sysop, count):
    """One source, normalised. Returns [] for anything that didn't work out —
    an unreachable source must never take the whole board down with it."""
    source = label_for(url)
    try:
        page, is_feed = _page_of(url)
    except Exception:
        return []
    if page is None:
        return []
    try:
        return _from_feed(page, source, count) if is_feed \
            else _from_page(page, source, count, sysop)
    except Exception:
        return []


# -- Merging ---------------------------------------------------------------


def _key(entry):
    """What makes two entries the same story: the article behind them, or
    failing that the headline. Wire stories land in several feeds verbatim,
    and a board that lists them twice just looks broken."""
    url = (entry.get("url") or "").strip().rstrip("/").lower()
    if url:
        return url
    return " ".join((entry.get("title") or entry["text"]).lower().split())


def merge(entries, count):
    """All sources as one board: newest first, duplicates dropped.

    Entries without a date keep their relative order and follow the dated
    ones — see the module docstring for why they aren't given one."""
    ordered = sorted(
        enumerate(entries),
        key=lambda pair: (pair[1]["ts"] is None,
                          -(pair[1]["ts"] or 0),
                          pair[0]),
    )
    out, seen = [], set()
    for _, entry in ordered:
        key = _key(entry)
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
        if len(out) >= count:
            break
    return out


def collect(urls, sysop, count):
    """Fetches every source and merges the lot into one dated board.

    Each source may contribute up to `count` entries so that a single busy
    feed cannot crowd out a quiet one before the merge has even happened —
    the cut to `count` is made afterwards, on the merged timeline."""
    entries = []
    for url in urls:
        entries.extend(fetch(url, sysop, count))
    return merge(entries, count)
