"""Load, parse pages and number links."""

import json
import re
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from bs4 import BeautifulSoup, NavigableString

from .constants import (
    BLOCK_TAGS, CONSENT_SELECTORS, HEADING_TAGS, MARKER_RE, MAX_IMAGES,
    MAX_LINKS, NOISE_ROLES, SKIP_SCHEMES, TEASER_MIN_CHARS,
    screen_lines, screen_width,
)
from .images import fetch_image, worth_fetching
from .tables import render_cards, render_infobox, render_table
from .i18n import t


class Page:
    def __init__(self, url, title):
        self.url = url
        self.title = title
        self.theme_color = ""     # <meta name="theme-color"> — for auto color mode
        self.logo_urls = []       # Logo candidates of page — become header banner
        self.feed_url = ""        # discovered RSS/Atom feed — for message base
        self.feed_items = []      # [{"title","url","ts","summary"}] — only feeds, ts may be None
        self.refresh_url = ""     # <meta http-equiv="refresh"> — redirect target
        self.firecrawl_error = "" # Firecrawl was on, failed — reason for user
        self.html = ""            # Raw document — kept for re-parsing
        self.is_search = False    # Search result list, not styled page
        self.low_text = False     # build_page found little text — candidate for re-scrape
        self.template_used = False # domain style template actually took hold here
        self.image_candidates = 0 # images worth showing that build_page found
        self.forms = []           # GET forms as input masks ('fm')
        self.blocks = []          # [{"type": "text"|"heading"|"pre"|"image", ...}]
        self.links = []           # [(url, label)] — index+1 = link number
        self._link_index = {}     # url -> number

    def add_link(self, url, label):
        if url in self._link_index:
            return self._link_index[url]
        if len(self.links) >= MAX_LINKS:
            return None
        self.links.append((url, label))
        num = len(self.links)
        self._link_index[url] = num
        return num

    def link_url(self, num):
        if 1 <= num <= len(self.links):
            return self.links[num - 1][0]
        return None


def block_text(block):
    """Block as plain text — for download and SysOp context.
    Tables and images carry their content in "lines" instead of "content";
    without this conversion they would silently fall through when saving."""
    if "content" in block:
        return block["content"]
    if block["type"] == "table":
        return "\n".join(block["lines"])
    if block["type"] == "image":
        return t("render.image_label", alt=block.get("alt", ""))
    return ""


def page_text(page):
    """Entire page as text, in document order."""
    return "\n\n".join(filter(None, (block_text(b) for b in page.blocks)))


def resolve_ddg(url):
    """Resolve DuckDuckGo redirect links (uddg=...) to actual target."""
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return url


def usable_href(href):
    return href and not href.startswith(SKIP_SCHEMES)


def aria_label(tag):
    label = tag.get("aria-label", "").strip()
    return label or None


BR_TOKEN = "\x00"                  # Placeholder for <br>, survives get_text(strip=True)
STYLE_HIDDEN_RE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)
# Classic noise containers: cookie banners, newsletters, share bars.
# Only full class/id tokens match — "content" must not match "consent".
NOISE_HINT_RE = re.compile(
    r"(?:^|[-_ ])(cookie\w*|consent|gdpr|newsletter|subscribe|paywall|promo\w*|"
    r"advert\w*|ads|breadcrumbs?|share|social|sidebar|related|recommend\w*|"
    r"comments?|popup|modal|overlay)(?:$|[-_ ])", re.I)
REFRESH_RE = re.compile(r"^\s*(\d+)[;,]\s*url\s*=\s*['\"]?([^'\"\s>]+)", re.I)


def number_links(page, root, base_url):
    """Number links under root: marker [n] right after link text.
    Links with no visible text (icons, logos) get no marker —
    they would otherwise appear as empty "[n]" lines ('l' lists them anyway)."""
    for a in root.find_all("a"):
        href = a.get("href")
        if not usable_href(href):
            continue
        label = a.get_text(" ", strip=True) or aria_label(a)
        if not label:
            continue
        # Already marked (nested blocks/tables) — no second [n].
        if MARKER_RE.search(label[-6:]):
            continue
        num = page.add_link(resolve_ddg(urljoin(base_url, href)), label)
        if num is not None:
            a.append(NavigableString(f"[{num}]"))


def mark_emphasis(tag):
    """Emphasis in Usenet convention: strong/b -> *bold*, em/i -> /italic/.
    Only for emphasis WITHIN a block — completely emphasized blocks
    (pure CSS styling cases) remain unmarked."""
    block_len = len(tag.get_text(" ", strip=True))
    for em in tag.find_all(["strong", "b", "em", "i"]):
        text = em.get_text(" ", strip=True)
        if not text or len(text) >= block_len:
            continue
        mark = "*" if em.name in ("strong", "b") else "/"
        em.replace_with(NavigableString(f"{mark}{text}{mark}"))


def img_src(tag):
    """Get image URL from lazy-load attributes and srcset too."""
    src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
    if not src:
        srcset = (tag.get("srcset") or tag.get("data-srcset") or "").strip()
        if srcset:
            src = srcset.split(",")[0].strip().split()[0]
    return src


LOGO_HINT_RE = re.compile(r"logo|wordmark|brandmark|site-?brand", re.I)
# PIL can't handle SVG, and .ico often has only 16x16 — neither works.
LOGO_BAD_EXT = (".svg", ".ico")


def _logo_candidate(src):
    if not src or src.startswith("data:"):
        return None
    return None if src.lower().split("?")[0].endswith(LOGO_BAD_EXT) else src


def _img_blob(img):
    return " ".join(filter(None, [
        img.get("src", ""), img.get("alt", ""), img.get("id", ""),
        " ".join(img.get("class") or []),
    ]))


GENERIC_LOGO_RE = re.compile(r"^[\w@-]*logo[\w@-]*$", re.I)


def _generic_logo_name(src):
    """Is the FILE itself simply named logo.png / site-logo@2x.png? That's the
    own brand — a third-party carries its name in the filename.

    Deliberately only the filename: if you check the whole text together,
    even an alt="Sportschau Logo" would make every third-party logo a generic match."""
    stem = (src or "").split("?")[0].rstrip("/").split("/")[-1].rsplit(".", 1)[0]
    return bool(GENERIC_LOGO_RE.match(stem))


def _links_home(img, base_url):
    """Does the image hang in a link to exactly this homepage? That's the
    most reliable sign of a logo — a page links its logo home, a teaser image doesn't.

    The comparison must match the own domain: accepting "any absolute URL"
    would have pulled partner logos from sportschau.de and ARD media library
    into tagesschau.de's footer."""
    a = img.find_parent("a")
    if not a:
        return False
    href = (a.get("href") or "").strip()
    if href in ("/", ""):
        return True
    target, home = urlparse(urljoin(base_url, href)), urlparse(base_url)
    return target.netloc == home.netloc and target.path.rstrip("/") == ""


def _icon_size(link):
    """Edge length from sizes="180x180". Without spec, sort to end."""
    m = re.match(r"\s*(\d+)\s*x\s*(\d+)", link.get("sizes") or "")
    return int(m.group(1)) if m else 0


def _icon_links(soup, kind):
    """<link rel=...icon...>, largest edge length first. Pages often provide
    half a dozen sizes; 57x57 is too small to read as a logo, 180x180 works."""
    links = [l for l in soup.find_all("link", rel=True)
             if kind in " ".join(l["rel"] if isinstance(l["rel"], list) else [l["rel"]]).lower()]
    return sorted(links, key=_icon_size, reverse=True)


def find_logos(soup, base_url, limit=4):
    """URLs of possible page logos, best first — for the ASCII banner.

    Must run *before* <header>/<nav> are discarded: that's where the logo hangs.
    Multiple candidates because the first often won't render (SVG, gradient,
    silhouette without inner detail); the caller tries them in order.

    Header is preferred: a "logo" hit anywhere in the body is often a partner
    or section logo from a teaser — that's how tagesschau.de got the Sportschau mark."""
    out = []

    def add(src):
        src = _logo_candidate(src)
        url = urljoin(base_url, src) if src else None
        if url and url not in out:
            out.append(url)

    brand = urlparse(base_url).netloc.removeprefix("www.").split(".")[0].lower()

    def is_own_logo(img):
        """Does the image carry THIS page's brand? "logo" in the name alone
        isn't enough — partner and section tiles are called the same
        ("Sportschau Logo" on tagesschau.de)."""
        blob = _img_blob(img)
        return bool(LOGO_HINT_RE.search(blob)) and (
            brand in blob.lower() or _generic_logo_name(img_src(img)))

    head = soup.find("header") or soup.find(attrs={"role": "banner"})
    for img in (head.find_all("img") if head else []):
        if _links_home(img, base_url) or is_own_logo(img):
            add(img_src(img))

    for link in _icon_links(soup, "apple-touch-icon"):
        add(link.get("href"))

    for img in soup.find_all("img"):
        if is_own_logo(img):
            add(img_src(img))

    # Large PNG favicons (192x192 from manifest) are often the brand mark.
    for link in _icon_links(soup, "icon"):
        add(link.get("href"))

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        for entry in (data if isinstance(data, list) else [data]):
            logo = isinstance(entry, dict) and entry.get("logo")
            if isinstance(logo, dict):
                logo = logo.get("url")
            if isinstance(logo, str):
                add(logo)
    return out[:limit]


def jsonld_article(soup):
    """Collects headline/articleBody/description from ld+json scripts —
    lifeline for JS pages that only deliver their text there."""
    best = {"headline": "", "articleBody": "", "description": ""}
    for sc in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        try:
            stack = [json.loads(sc.string or "")]
        except (ValueError, TypeError):
            continue
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                stack.extend(v for v in node.values() if isinstance(v, (list, dict)))
                for key in best:
                    val = node.get(key)
                    if isinstance(val, str) and len(val.strip()) > len(best[key]):
                        best[key] = val.strip()
    return best


def table_rows(table):
    """Table rows as cell lists — only this level's cells,
    nested table cells don't belong here."""
    rows = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [c.get_text(" ", strip=True).replace(BR_TOKEN, " ")
                 for c in tr.find_all(["th", "td"]) if c.find_parent("table") is table]
        if any(cells):
            rows.append(cells)
    return rows


def is_data_table(table, rows):
    """Distinguish real data tables from layout tables. Old pages (and
    Hacker News) build their entire layout from tables — they must not
    end up in a frame, or the text falls apart."""
    # Nested tables on old pages are almost always
    # layout structure (Hacker News builds its whole sheet from them).
    if table.find("table") is not None or table.find_parent("table") is not None:
        return False
    if len(rows) < 2:
        return False
    cols = max(len(r) for r in rows)
    if cols < 2:
        return False
    # A regular grid suggests data; ragged rows
    # are almost always layout.
    if sum(1 for r in rows if len(r) == cols) < max(2, int(0.8 * len(rows))):
        return False
    # Whole paragraphs in cells: that's text layout, not a table.
    return max(len(c) for r in rows for c in r) <= 200


def table_block(page, table, base_url):
    """Render real data tables as ASCII tables; layout tables and
    tables too wide return None and pass through as normal blocks."""
    rows = table_rows(table)
    if not is_data_table(table, rows):
        return None
    lines = render_table(rows, bool(table.find("th")), screen_width())
    if lines is None:
        return None
    number_links(page, table, base_url)   # now — otherwise markers without table
    rows = table_rows(table)              # cells now include [n] markers
    lines = render_table(rows, bool(table.find("th")), screen_width())
    return {"type": "table", "lines": lines} if lines else None


INFOBOX_HINT_RE = re.compile(r"\binfobox\b|\bvcard\b|\bsidebar\b", re.I)


def infobox_rows(table):
    """Profile rows of an infobox as (label, value). A row with only
    one cell becomes a subheading (label None). Returns [] if
    the table is not a profile — then it runs the normal path."""
    if not INFOBOX_HINT_RE.search(_classes(table)):
        return []
    rows = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [c for c in tr.find_all(["th", "td"]) if c.find_parent("table") is table]
        texts = [c.get_text(" ", strip=True).replace(BR_TOKEN, " ") for c in cells]
        texts = [re.sub(r"\s+", " ", x).strip() for x in texts]
        if len(texts) == 1 and texts[0]:
            rows.append((None, texts[0]))
        elif len(texts) >= 2 and (texts[0] or texts[1]):
            rows.append((texts[0], " ".join(filter(None, texts[1:]))))
    # A single title is not a profile.
    return rows if sum(1 for l, _ in rows if l) >= 2 else []


def infobox_block(page, table, base_url):
    """Render infobox as profile box; None if it's not one."""
    if not infobox_rows(table):
        return None
    number_links(page, table, base_url)   # now — otherwise markers without box
    lines = render_infobox(infobox_rows(table), screen_width())
    return {"type": "table", "lines": lines} if lines else None


GRID_HINT_RE = re.compile(r"grid|card|tile|teaser|kachel", re.I)
GRID_PLACEHOLDER = "bbs-cards"   # Marker tag, holds grid at its text position
GRID_MIN_ITEM = 25               # shorter tiles are navigation, not content


def _classes(tag):
    val = tag.get("class") or []
    return " ".join(val) if isinstance(val, list) else str(val)


def _attached(tag, root):
    """Does tag still hang under root? Replaced grid containers take their
    whole subtree out of the document — their children should be ignored."""
    node = tag
    while node is not None:
        if node is root:
            return True
        node = node.parent
    return False


def grid_items(container):
    """Tiles of a CSS grid as text list — deliberately only for grids
    whose tiles have NO inner blocks. Otherwise the normal parser
    completely misses such tiles; grids from <h2>/<p> stay untouched
    and continue to render as headlines. Returns [] if container is not a recognizable grid."""
    if not GRID_HINT_RE.search(_classes(container)):
        return []
    kids = [c for c in container.find_all(recursive=False)
            if c.name in ("div", "li", "article", "section")]
    if len(kids) < 3 or len({c.name for c in kids}) > 1:
        return []
    items = []
    for kid in kids:
        if kid.find(BLOCK_TAGS) is not None or kid.find("table") is not None:
            return []
        txt = kid.get_text(" ", strip=True).replace(BR_TOKEN, " ")
        # Tiles should catch teaser text, not navigation chips or
        # page numbers — those already appear elsewhere as link lists.
        if not (GRID_MIN_ITEM <= len(MARKER_RE.sub("", txt).strip()) <= 300):
            return []
        items.append(txt)
    return items


READABILITY_MIN_TEXT = 400   # shorter winners are not worth it
READABILITY_MIN_SHARE = 0.2  # ... and must make up part of the page


def _link_density(tag):
    """Share of text that's in links. Navigation blocks approach 1."""
    total = len(tag.get_text(" ", strip=True))
    if not total:
        return 1.0
    linked = sum(len(a.get_text(" ", strip=True)) for a in tag.find_all("a"))
    return min(linked / total, 1.0)


def _paragraph_score(text):
    """Points of a paragraph: length plus commas — flowing text has both,
    menu items and teaser lines have neither."""
    if len(text) < 25:
        return 0.0
    return 1.0 + text.count(",") + min(len(text) / 100.0, 3.0)


def readable_root(soup):
    """Reading view by Readability method: each paragraph passes its
    points to parents and grandparents; the highest-scoring container with low
    link density wins. Returns None if no candidate convinces — then
    the previous selection stays (<main>, <article>, whole page).

    This handles the many pages that set neither <main> nor role="main"
    and tuck their article in an anonymous <div>."""
    scores = {}
    for para in soup.find_all(["p", "pre", "blockquote"]):
        score = _paragraph_score(para.get_text(" ", strip=True))
        if not score:
            continue
        # Direct container counts full, parent above half, third a
        # third — so the tightest container that contains everything wins.
        node, weight = para.parent, 1.0
        for _ in range(3):
            if node is None or node.name in (None, "[document]", "html", "body"):
                break
            entry = scores.setdefault(id(node), [node, 0.0])
            entry[1] += score * weight
            node, weight = node.parent, weight / 2

    if not scores:
        return None
    total_text = len(soup.get_text(" ", strip=True))
    best, best_score = None, 0.0
    for node, score in scores.values():
        score *= 1.0 - _link_density(node)
        if score > best_score:
            best, best_score = node, score
    if best is None:
        return None
    text = len(best.get_text(" ", strip=True))
    if text < READABILITY_MIN_TEXT or text < total_text * READABILITY_MIN_SHARE:
        return None
    return best


def salvage_leaf_text(soup, min_chars=25, limit=60):
    """Cull text from div/span leaves — for pages without block tags.

    JS apps (Instagram & Co.) build the whole page from <div> and <span>;
    the normal pass over BLOCK_TAGS finds nothing. Here we take
    leaves (no container children anymore) with enough text, deduplicated
    and in document order. Short stuff (buttons, labels) falls through
    the minimum length sieve."""
    seen, out = set(), []
    for tag in soup.find_all(["div", "span", "h1", "h2", "h3"]):
        if tag.find(["div", "span", "p", "ul", "section", "table"]) is not None:
            continue
        txt = tag.get_text(" ", strip=True)
        if len(txt) >= min_chars and txt not in seen:
            seen.add(txt)
            out.append(txt)
            if len(out) >= limit:
                break
    return out


def mark_big_title(page):
    """Find the top title of the page and mark it as big
    poster title (big=True) — so the renderer renders it in the block font of the
    intro logo. Only the first heading gets big; others stay plain bold so the
    page doesn't disappear under a chain of giant titles."""
    if any(b["type"] == "banner" for b in page.blocks):
        return page
    for b in page.blocks:
        if b["type"] == "heading":
            b["big"] = True
            break
    return page


_CONSENT_SELECTOR = ", ".join(CONSENT_SELECTORS)


def strip_consent(soup):
    """Remove cookie banners without replacement.

    Unlike the general noise filter, this works without the
    half-page brake: the containers of major consent platforms never carry
    page content, and precisely the annoying full-screen modals would
    trigger the brake otherwise and stay put. Nothing is consented to here —
    the banner vanishes, consent remains ungranted.

    All patterns run as a selector list, so in one pass through the
    document; if that fails, individual patterns are tried, so one
    indigestible pattern doesn't prevent the whole cleanup."""
    try:
        hits = soup.select(_CONSENT_SELECTOR)
    except Exception:
        hits = []
        for sel in CONSENT_SELECTORS:
            try:
                hits.extend(soup.select(sel))
            except Exception:
                continue
    for tag in hits:
        if not tag.decomposed:
            tag.decompose()


STYLE_PLACEHOLDER = "bbs-styled"   # marker tag for a style-template element

# Block kinds that completely REPLACE an element. The other marks (text,
# quote) are only hints for the normal evaluation of child elements.
REPLACING_KINDS = {"banner", "heading", "topicbar", "plaque", "notice",
                   "ticker", "frame", "rule", "pre", "infobox"}


def _protected_chain(node):
    """The marked element and all its ancestors — this chain must survive
    every cleanup step, or the content falls with the noise."""
    out = set()
    while node is not None:
        out.add(id(node))
        node = node.parent
    return out


def _styled_blocks(page, soup, base_url, styled):
    """Replace the elements marked by the template with placeholders, which
    the main pass then turns into blocks at their position in the document.
    That preserves page order, and everything else keeps running through the
    normal heuristics."""
    from . import styletpl

    for tag in soup.find_all(attrs={styletpl.MARK_ATTR: True}):
        if tag.decomposed:
            continue
        kind = tag.get(styletpl.MARK_ATTR)
        if kind not in REPLACING_KINDS:
            continue
        # Marks hanging inside an already replaced element are done.
        if not _attached(tag, soup):
            continue
        # A component collapses its element into ONE text block — an image
        # inside it would be swallowed. Titles carry no pictures, so this
        # only ever fires when the mark grabbed a container: it is refused,
        # the element runs through the normal pass and keeps its image.
        if kind != "pre" and tag.find("img") is not None:
            continue
        if kind == "rule":
            block = {"type": "rule", "content": ""}
        elif kind == "pre":
            block = {"type": "pre", "content": tag.get_text().replace(BR_TOKEN, "\n").rstrip()}
        elif kind == "infobox":
            rows = infobox_rows(tag) if tag.name == "table" else _dl_rows(tag)
            lines = render_infobox(rows, screen_width()) if rows else None
            if not lines:
                continue
            number_links(page, tag, base_url)
            block = {"type": "table", "lines": lines}
        else:
            number_links(page, tag, base_url)
            txt = " ".join(
                s.strip() for s in tag.get_text(" ", strip=True).split(BR_TOKEN) if s.strip()
            )
            if not MARKER_RE.sub("", txt).strip(" .,|-·"):
                continue
            block = {"type": kind, "content": txt}
        placeholder = BeautifulSoup("", "html.parser").new_tag(STYLE_PLACEHOLDER)
        styled[id(placeholder)] = block
        tag.replace_with(placeholder)


def _dl_rows(tag):
    """<dl> pairs as key/value rows for the info box."""
    dl = tag if tag.name == "dl" else tag.find("dl")
    if dl is None:
        return []
    rows = []
    for dt in dl.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd is not None:
            rows.append([dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)])
    return rows[:30]


def _style_hint(tag, soup):
    """Is this block inside a region the template marked as a quote? text
    and quote replace nothing — they only colour how the children below
    them are set."""
    from . import styletpl

    node = tag
    while node is not None and node is not soup:
        kind = node.get(styletpl.MARK_ATTR) if hasattr(node, "get") else None
        if kind in ("text", "quote"):
            return kind == "quote"
        node = node.parent
    return False


def build_page(html, base_url, render_images=True, img_width=60, img_mode="blocks",
               template=None, js_rendered=None):
    """Read the page in document order and number all links.
    With `template` (the domain's learned style template, see styletpl.py)
    CSS selectors decide content root, noise and BBS style elements;
    everything not matched by a rule continues through normal heuristics.

    `js_rendered` records how the HTML reached us — True if a JS renderer
    (Firecrawl or Playwright) already ran the page, False for a bare HTTP
    fetch, None if the caller doesn't know. It only steers the wording of the
    too-little-text hint (see _low_text_message)."""
    soup = BeautifulSoup(html, "html.parser")
    jsonld = jsonld_article(soup)  # collect before discarding scripts
    logo_urls = find_logos(soup, base_url)  # ditto — logo hangs in <header>

    # Measure GET forms while <form> tags still exist — right
    # after they disappear with the scripts from the document.
    from .forms import extract_forms
    form_masks = extract_forms(soup, base_url)

    # <noscript> is VISIBLE to us — we're the browser without JavaScript.
    for tag in soup.find_all("noscript"):
        tag.unwrap()
    for tag in soup(["script", "style", "svg", "form"]):
        tag.decompose()
    strip_consent(soup)

    # The style template goes first: it throws away its own noise, marks the
    # style elements and names the content root. Its ancestor chain is
    # protected from the cleanup steps below — otherwise the blanket
    # header/nav/footer sweep could wipe the very thing it points at.
    tpl_root, protected = None, set()
    if template:
        from . import styletpl
        root = styletpl.apply_to(soup, template)
        if root is not soup and root is not None and not root.decomposed:
            tpl_root = root
            protected = _protected_chain(root)

    for tag in soup(["header", "nav", "footer", "aside"]):
        if id(tag) not in protected and not tag.decomposed:
            tag.decompose()

    # Parse ARIA if present: hidden elements and
    # landmark roles (navigation, banner, ...) are not page content.
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        if not tag.decomposed:
            tag.decompose()
    for tag in soup.find_all(hidden=True):
        if not tag.decomposed:
            tag.decompose()
    for tag in soup.find_all(style=STYLE_HIDDEN_RE):
        if not tag.decomposed:
            tag.decompose()
    role_total = len(soup.get_text())
    for tag in soup.find_all(attrs={"role": True}):
        # decompose() of an ancestor destroys this tag too (attrs=None).
        if tag.decomposed or id(tag) in protected:
            continue
        if (tag.get("role") or "").lower() in NOISE_ROLES:
            # Half-page brake: Instagram & Co. render the POST as
            # role="dialog" modal — whoever holds most of the text is
            # content, not a cookie banner.
            if len(tag.get_text()) >= max(role_total, 1) * 0.5:
                continue
            tag.decompose()

    # Reading view: containers that already say via class/id that they're noise.
    # The half-page brake prevents an unfortunately named
    # main container ("main-content-sidebar") from dragging the article along.
    total_text = len(soup.get_text())
    for tag in soup.find_all(["div", "section", "ul"]):
        if tag.decomposed or id(tag) in protected:
            continue
        blob = _classes(tag) + " " + (tag.get("id") or "")
        if NOISE_HINT_RE.search(blob) and len(tag.get_text()) < max(total_text, 1) * 0.5:
            tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else base_url
    page = Page(base_url, title)
    page.html = html    # fuers spaetere Lernen/Neusetzen mit einem Stilprofil
    # Remembered on the page so rebuilds from page.html (template brake,
    # restyle) keep picking the right too-little-text wording.
    page.js_rendered = js_rendered
    page.logo_urls = logo_urls
    page.forms = form_masks
    meta = soup.find("meta", attrs={"name": "theme-color"})
    if meta:
        page.theme_color = meta.get("content", "").strip()
    feed = soup.find("link", type=lambda t: t and ("rss" in t or "atom" in t))
    if feed and feed.get("href"):
        page.feed_url = urljoin(base_url, feed["href"])
    refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    if refresh:
        m = REFRESH_RE.match(refresh.get("content", ""))
        if m and int(m.group(1)) <= 10:
            page.refresh_url = urljoin(base_url, m.group(2))

    # The template's content root beats every heuristic — it was learned
    # for exactly this site.
    if tpl_root is not None and not tpl_root.decomposed and tpl_root.get_text(strip=True):
        main = tpl_root
    else:
        # Prefer role="main" / <main> as content root; second tier is
        # a single <article> (mini-reader mode against sidebar noise).
        main = soup.find("main") or soup.find(attrs={"role": "main"})
        if not main:
            articles = soup.find_all("article")
            if len(articles) == 1:
                main = articles[0]
        # Third tier: pages without both get the Readability scorer.
        if not main:
            main = readable_root(soup)
    if main and main.get_text(strip=True):
        soup = main

    for br in soup.find_all("br"):
        br.replace_with(NavigableString(BR_TOKEN))

    # Turn the template's style elements into placeholders — they then stand
    # at their correct position in the document and are rendered below.
    styled = {}
    if template:
        _styled_blocks(page, soup, base_url, styled)
    # Did the template actually take hold — or did the fit check refuse it
    # and the heuristic quietly do the work? The browser says so on dialing,
    # so nobody wonders why a page looks like every other one.
    page.template_used = bool(template) and (tpl_root is not None or bool(styled))

    # Pre-collapse CSS grids into placeholders so they end up at
    # their correct position in the document in the pass below.
    grids = {}
    for container in soup.find_all(["div", "ul", "section"]):
        if not _attached(container, soup):   # was in an already replaced grid
            continue
        # A style element of the template trumps tile detection — otherwise
        # the card set would squander what the template explicitly set.
        if container.find(STYLE_PLACEHOLDER) is not None:
            continue
        items = grid_items(container)
        if not items:
            continue
        number_links(page, container, base_url)
        items = grid_items(container) or items   # jetzt mit [n]-Markern
        lines = render_cards(items, screen_width())
        if lines:
            placeholder = BeautifulSoup("", "html.parser").new_tag(GRID_PLACEHOLDER)
            grids[id(placeholder)] = lines
            container.replace_with(placeholder)

    image_count = 0
    seen_text = set()
    rendered_tables = set()

    for tag in soup.find_all(
        BLOCK_TAGS + ["a", "img", "table", "hr", GRID_PLACEHOLDER, STYLE_PLACEHOLDER]
    ):
        if tag.name == GRID_PLACEHOLDER:
            page.blocks.append({"type": "table", "lines": grids[id(tag)]})
            continue

        if tag.name == STYLE_PLACEHOLDER:
            page.blocks.append(styled[id(tag)])
            continue

        if tag.name == "img":
            if image_count >= MAX_IMAGES:
                continue
            src = img_src(tag)
            if not src or src.startswith("data:"):
                continue
            alt = tag.get("alt", "").strip() or aria_label(tag) or t("page.image_alt_default")
            # Skip images not worth showing (icons, logos, tracking pixels).
            if not worth_fetching(src, alt, tag.get("width"), tag.get("height")):
                continue
            # Counted BEFORE the fetch and regardless of the image setting:
            # this is the yardstick a style template is measured against.
            # Learning runs without images (too slow), so without this count
            # a template could throw every picture off the page and still
            # pass its proof.
            page.image_candidates += 1
            if not render_images:
                continue
            full_url = urljoin(base_url, src)
            # Cap image height to one screen (lines minus label and blank line
            # below), so label + image fit on one screen
            # and the pager never cuts them.
            img_max_lines = max(1, screen_lines() - 2)
            art = fetch_image(full_url, width=img_width, mode=img_mode, max_lines=img_max_lines)
            if art:
                page.blocks.append({"type": "image", "alt": alt, **art})
                image_count += 1
            continue

        if tag.name == "hr":
            page.blocks.append({"type": "pre", "content": "─" * 40})
            continue

        # Teaser tiles without block tag. News portals and SPAs hang the
        # headline as <a><div><span>Title</span></div></a> — no
        # BLOCK_TAG anywhere, so without this branch it falls through completely
        # and lands silently in the link list (blick.ch: only section titles
        # remained). Links WITHIN a block continue through number_links,
        # otherwise the headline would appear twice.
        if tag.name == "a":
            if tag.find(BLOCK_TAGS) or tag.find_parent(BLOCK_TAGS + ["a"]):
                continue
            href = tag.get("href")
            if not usable_href(href):
                continue
            txt = " ".join(
                s.strip() for s in tag.get_text(" ", strip=True).split(BR_TOKEN) if s.strip()
            )
            if len(txt) < TEASER_MIN_CHARS or txt in seen_text:
                continue
            seen_text.add(txt)
            num = page.add_link(resolve_ddg(urljoin(base_url, href)), txt)
            page.blocks.append(
                {"type": "text", "content": txt + (f" [{num}]" if num else "")}
            )
            continue

        # Everything within an already rendered table is done —
        # including nested tables and their cells.
        if any(id(p) in rendered_tables for p in tag.find_parents("table")):
            continue

        if tag.name == "table":
            block = infobox_block(page, tag, base_url) or table_block(page, tag, base_url)
            if block is not None:
                rendered_tables.add(id(tag))
                page.blocks.append(block)
            continue

        # Skip nested blocks to avoid duplicates.
        if tag.find(BLOCK_TAGS):
            continue

        number_links(page, tag, base_url)
        if tag.name not in HEADING_TAGS and tag.name != "pre":
            mark_emphasis(tag)

        txt = tag.get_text(" ", strip=True)
        # Skip blocks with no real content (only markers/punctuation).
        if not MARKER_RE.sub("", txt).strip(" .,|-·" + BR_TOKEN):
            continue
        if txt in seen_text:
            continue
        seen_text.add(txt)

        # Many pages put the link AROUND the block (<a><h2>Title</h2></a>) —
        # then the block itself carries the marker, otherwise the
        # headline stays without a selectable number.
        if tag.name != "pre" and not MARKER_RE.search(txt):
            anchor = tag.find_parent("a")
            href = anchor.get("href") if anchor else None
            if usable_href(href):
                num = page.add_link(resolve_ddg(urljoin(base_url, href)), txt)
                if num is not None:
                    txt += f" [{num}]"

        if tag.name == "pre":
            page.blocks.append({"type": "pre", "content": tag.get_text().replace(BR_TOKEN, "\n").rstrip()})
            continue
        if tag.name in HEADING_TAGS:
            for seg in filter(None, (s.strip() for s in txt.split(BR_TOKEN))):
                page.blocks.append({"type": "heading", "content": seg})
            continue

        # Text/quote marks of the template are hints for child blocks: they
        # replace nothing, they only decide whether the block is quoted.
        hint_quote = _style_hint(tag, soup) if template else False
        quoted = (
            hint_quote
            or tag.name == "blockquote"
            or tag.find_parent("blockquote") is not None
        )
        prefix = ""
        if tag.name == "li":
            lst = tag.find_parent(["ol", "ul"])
            if lst is not None and lst.name == "ol":
                prefix = f"{len(tag.find_previous_siblings('li')) + 1}. "
            else:
                prefix = "· "
        if quoted:
            prefix = "> " + prefix
        # <br> divides the block into its own lines (poems, addresses, chatlogs).
        cont = "> " if quoted else ("  " if tag.name == "li" else "")
        segments = [s for s in (s.strip() for s in txt.split(BR_TOKEN)) if s] or [""]
        for i, seg in enumerate(segments):
            block = {"type": "text", "content": (prefix if i == 0 else cont) + seg}
            if tag.name == "li":
                block["tight"] = True   # List items without blank lines between
            page.blocks.append(block)

    # Still collect remaining links (outside text blocks),
    # so "l" can offer them — e.g., pure link lists in <div>s.
    for a in soup.find_all("a"):
        href = a.get("href")
        if not usable_href(href):
            continue
        label = a.get_text(" ", strip=True) or aria_label(a)
        if label:
            page.add_link(resolve_ddg(urljoin(base_url, href)), label)

    # block_text instead of b["content"]: tables/grids carry their text in
    # "lines" — a pure table page is not "thin".
    text_chars = sum(len(block_text(b)) for b in page.blocks)
    if text_chars < 200:
        # Lifeline: JS-heavy pages often deliver the article only in
        # ld+json — we show that instead of the text-too-thin warning.
        body = jsonld["articleBody"] or jsonld["description"]
        if body:
            if jsonld["headline"]:
                page.blocks.append({"type": "heading", "content": jsonld["headline"]})
            for para in filter(None, (p.strip() for p in body.splitlines())):
                page.blocks.append({"type": "text", "content": para})
        else:
            # Second lifeline: div/span soups (Instagram & Co.) have no
            # semantic block tags — then cull text from the leaves.
            for txt in salvage_leaf_text(soup):
                page.blocks.append({"type": "text", "content": txt})
        if sum(len(block_text(b)) for b in page.blocks) < 200:
            page.low_text = True
            page.blocks.append({
                "type": "text",
                "content": _low_text_message(js_rendered),
            })
    return mark_big_title(page)


def _low_text_message(js_rendered):
    """Pick the too-little-text hint that matches how the page was fetched.

    A page that already went through a JS renderer (Firecrawl or Playwright)
    had its JavaScript run — nagging the user to "try --firecrawl" there would
    be wrong. Only when nothing rendered the JS, and no local renderer is even
    installed, do we point at the ways to get one."""
    from . import jsrender
    if js_rendered is None:
        js_rendered = jsrender.available()
    if js_rendered:
        return t("page.low_text_warning_rendered")
    if not jsrender.available():
        return t("page.low_text_warning_no_js")
    return t("page.low_text_warning")


MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def page_from_markdown(md, url):
    """Build a page with numbered links from Firecrawl markdown."""
    page = Page(url, url)
    for raw in md.splitlines():
        line = MD_IMAGE_RE.sub("", raw.strip())

        def _link(m):
            num = page.add_link(m.group(2), m.group(1))
            return f"{m.group(1)}[{num}]" if num else m.group(1)

        line = MD_LINK_RE.sub(_link, line).strip()
        if not line or not line.strip("#*-_ "):
            continue
        if line.startswith("#"):
            page.blocks.append({"type": "heading", "content": line.lstrip("# ").strip()})
        else:
            page.blocks.append({"type": "text", "content": line.lstrip("*- ").strip()})
    for b in page.blocks:
        if b["type"] == "heading":
            page.title = b["content"]
            break
    return mark_big_title(page)
