"""RSS/Atom as a 'message base': feeds become classic BBS menus."""

import contextlib
import datetime as _dt
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from .constants import USER_AGENT
from .i18n import t

TAG_RE = re.compile(r"<[^>]+>")
MAX_ITEMS = 30

# Where the two feed dialects keep the publication date.
DATE_TAGS = ("pubdate", "date", "published", "updated", "modified")


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _clean(html):
    return TAG_RE.sub("", html).replace("&amp;", "&").replace("&quot;", '"').strip()


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def timestamp(raw):
    """A feed date as epoch seconds — None when the feed didn't say.

    Two dialects are in the wild: RFC 822 in RSS ("Tue, 21 Jul 2026 08:12:00
    +0200") and ISO 8601 in Atom ("2026-07-21T08:12:00Z"). A date without a
    zone is read as UTC, so entries from different feeds stay comparable
    instead of silently drifting by the local offset."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for parse in (parsedate_to_datetime,
                  lambda s: _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))):
        with contextlib.suppress(Exception):
            moment = parse(raw)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=_dt.timezone.utc)
            return moment.timestamp()
    return None


def parse_feed(content, url):
    """Builds a page with numbered links from RSS/Atom XML."""
    from .page import Page
    root = ET.fromstring(content)
    page = Page(url, t("feeds.message_base"))

    items = []
    if _local(root.tag) == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is not None:
            page.title = _text(channel.find("title")) or page.title
        for item in root.iter():
            if _local(item.tag) != "item":
                continue
            title = link = desc = date = ""
            for child in item:
                name = _local(child.tag)
                if name == "title":
                    title = _text(child)
                elif name == "link":
                    link = _text(child)
                elif name == "description":
                    desc = _text(child)
                elif name.lower() in DATE_TAGS and not date:
                    date = _text(child)
            items.append((title, link, desc, timestamp(date)))
    else:  # Atom
        for child in root:
            if _local(child.tag) == "title":
                page.title = _text(child) or page.title
        for entry in root.iter():
            if _local(entry.tag) != "entry":
                continue
            title = link = desc = date = ""
            for child in entry:
                name = _local(child.tag)
                if name == "title":
                    title = _text(child)
                elif name == "link" and not link:
                    link = child.get("href", "")
                elif name in ("summary", "content"):
                    desc = desc or _text(child)
                elif name.lower() in DATE_TAGS:
                    # 'published' wins over 'updated': a corrected typo
                    # shouldn't push an old entry back to the top.
                    if name.lower() == "published" or not date:
                        date = _text(child)
            items.append((title, link, desc, timestamp(date)))

    page.blocks.append({"type": "heading", "content": t("feeds.message_base_heading", title=page.title)})
    for title, link, desc, ts in items[:MAX_ITEMS]:
        if not title or not link:
            continue
        num = page.add_link(link, title)
        marker = f"[{num}]" if num else ""
        page.blocks.append({"type": "text", "content": f"{title}{marker}"})
        snippet = _clean(desc)[:160]
        if snippet:
            page.blocks.append({"type": "text", "content": snippet})
        # Kept alongside the rendered page so the bulletin board can sort
        # entries from several feeds into one timeline.
        page.feed_items.append({"title": title.strip(), "url": link,
                                "ts": ts, "summary": snippet})
    return page


def fetch_feed(url):
    # Some CDNs (e.g. Akamai on blick.ch) block Mozilla-like UAs on feed
    # URLs with a 403, but serve fine without a browser UA — hence the retry.
    last_err = None
    for headers in ({"User-Agent": USER_AGENT}, {}):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return parse_feed(resp.content, url), None
        except ET.ParseError as e:
            return None, t("feeds.parse_error", error=str(e))
        except requests.HTTPError as e:
            last_err = e
        except Exception as e:
            return None, t("feeds.fetch_error", error=str(e))
    return None, t("feeds.fetch_error", error=str(last_err))
