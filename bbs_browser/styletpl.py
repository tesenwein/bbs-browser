"""Style templates: learned ONCE per domain, then applied purely locally.

The predecessor (aipage.py) pushed EVERY page through the AI and cached the
finished markdown per URL — expensive and slow, and the very first visit to
any page always waited on the model. Here the AI instead learns ONE template
per domain: CSS selectors pointing at the renderer's BBS style elements
(poster banner, section bar, plaque, callout, framed box, rule, ...). The
template lands in the DB and every further page of that domain is rendered
without any AI call at all.

Three things keep this honest:

* The verification loop — a draft isn't judged on the page it was written
  for. Up to VERIFY_LINKS further pages of the same domain are fetched and
  `preview` reports the draft's text balance on ALL of them. A template that
  only fits the page it was born on never passes.
* The fit check (`coverage`) — before a template is applied, its OWN
  selectors are counted against the page. Hit too few of them and the page
  is left to the heuristic instead of being torn apart.
* The validation (`sanitize`) — only known block kinds and selectors that
  soupsieve can actually compile survive.
"""

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from . import db

VERSION = 1
MAX_RULES = 14
MAX_DROP = 30
COVERAGE_MIN = 0.4      # share of the template's own selectors that must hit
VERIFY_LINKS = 3        # how many further pages of the domain a draft is tested on

# The board's type case: every graphic component the renderer can actually
# set, and nothing beyond it. A template points selectors at these — it
# cannot invent a component. `drop` isn't a component but the instruction
# to discard.
BLOCK_KINDS = {
    "banner",    # block-letter poster title (like the intro logo)
    "heading",   # plain bold heading with an underline
    "topicbar",  # section bar with the title set into the rule
    "plaque",    # single-line box with a drop shadow — the nailed-up sign
    "notice",    # callout on a solid left bar with a bang
    "ticker",    # dimmed one-liner between arrows (dateline, kicker, byline)
    "frame",     # text inside a double ANSI box (lead, key statement)
    "infobox",   # key/value box built from a table or <dl>
    "rule",      # decorative divider line
    "quote",     # indented quote block
    "pre",       # untouched preformatted/code block
    "text",      # normal body text
    "drop",      # discard the element
}

MARK_ATTR = "data-bbs-block"


def domain_of(url):
    """Domain without "www." — empty for non-http(s) URLs (gopher/gemini,
    internal screens), which have no HTML and therefore no template."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        return ""
    return parsed.netloc.removeprefix("www.").lower()


# -- Fit: does the template grip this page? ---------------------------------


def coverage(soup, template):
    """(hits, total) over the template's OWN selectors: the content root and
    every rule. `drop` selectors are left out — noise that isn't on this page
    says nothing about the fit.

    This deliberately replaces the earlier layout fingerprint. That one
    compared the WHOLE document against the page the template was born on,
    so a front page full of teasers and one article of the same site barely
    overlapped and the template was refused on exactly the pages it was
    meant for. What matters isn't whether two pages look alike — it's
    whether the selectors we are about to apply find anything."""
    sels = [rule["sel"] for rule in template.get("rules") or [] if rule.get("block") != "drop"]
    if template.get("content"):
        sels.append(template["content"])
    hits = total = 0
    for sel in sels:
        try:
            found = soup.select_one(sel) is not None
        except Exception:
            # A selector soupsieve can't compile says nothing about the fit —
            # counting it as a miss would push a stored template below the
            # threshold on every page forever.
            continue
        total += 1
        if found:
            hits += 1
    return hits, total


def _as_soup(html_or_soup):
    if isinstance(html_or_soup, str):
        return BeautifulSoup(html_or_soup, "html.parser")
    return html_or_soup


# -- Blueprint for the AI ---------------------------------------------------


_OUTLINE_SKIP = {"script", "style", "svg", "path", "noscript", "meta", "link", "br"}


def outline(html_or_soup, max_lines=160, max_depth=7):
    """A textual blueprint of the page for the AI: tags with classes/IDs and
    the amount of text underneath them — but WITHOUT the text itself. Keeps
    the request small (a few hundred tokens instead of the whole page) and
    makes the result page-independent: what's learned is the structure, not
    the content."""
    soup = _as_soup(html_or_soup)
    root = soup.body or soup
    lines = []

    def walk(tag, depth):
        if len(lines) >= max_lines or depth > max_depth:
            return
        for child in tag.find_all(True, recursive=False):
            if child.name in _OUTLINE_SKIP:
                continue
            if len(lines) >= max_lines:
                return
            desc = child.name
            ident = child.get("id")
            if ident:
                desc += f"#{ident}"
            for c in (child.get("class") or [])[:3]:
                desc += f".{c}"
            chars = len(child.get_text(" ", strip=True))
            lines.append(f"{'  ' * depth}{desc}  [{chars}z]")
            if chars:
                walk(child, depth + 1)

    walk(root, 0)
    return "\n".join(lines)


# -- Validate and clean a draft ---------------------------------------------


def _valid_selector(soup, sel):
    """Only selectors soupsieve can actually compile. A broken selector
    would otherwise throw later, in the middle of building a page."""
    if not isinstance(sel, str) or not sel.strip() or len(sel) > 200:
        return False
    try:
        soup.select(sel, limit=1)
    except Exception:
        return False
    return True


def sanitize(raw, soup=None):
    """Turns the AI's answer into a template that can be trusted — or None."""
    if isinstance(raw, str):
        raw = parse_json(raw)
    if not isinstance(raw, dict):
        return None
    probe = soup if soup is not None else BeautifulSoup("<html></html>", "html.parser")

    content = raw.get("content")
    if not _valid_selector(probe, content):
        content = ""

    drop = [s for s in raw.get("drop") or [] if _valid_selector(probe, s)][:MAX_DROP]

    rules = []
    for r in raw.get("rules") or []:
        if not isinstance(r, dict):
            continue
        sel, kind = r.get("sel"), (r.get("block") or "").strip().lower()
        if kind not in BLOCK_KINDS or not _valid_selector(probe, sel):
            continue
        rules.append({"sel": sel, "block": kind})
        if len(rules) >= MAX_RULES:
            break

    if not content and not drop and not rules:
        return None   # a template without a single statement isn't one
    return {
        "version": VERSION,
        "content": content,
        "drop": drop,
        "rules": rules,
        "note": str(raw.get("note") or "")[:200],
    }


_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_json(text):
    """Extracts the JSON object from an AI answer (including from ```json
    fences)."""
    if not text:
        return None
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


# -- Apply ------------------------------------------------------------------


# Content brake. banner/heading/frame/rule collapse the WHOLE matched
# element into a single block — aimed at a container instead of a title,
# they swallow everything below. So each of them carries a text ceiling:
# above it the mark is refused and the element keeps running through the
# normal heuristics. A template can restyle titles, it cannot make body
# copy disappear.
KIND_MAX_CHARS = {
    "banner": 120,     # a poster title in block letters, nothing more
    "heading": 200,    # a heading, not a paragraph
    "topicbar": 60,    # has to fit into the rule
    "ticker": 120,     # one line: dateline, kicker, byline
    "rule": 120,       # collapses to a divider line — must carry no content
    "notice": 600,     # a note, not a chapter
    "plaque": 600,     # the sign carries a key statement
    "frame": 900,      # a lead may be a few sentences
    "pre": 8000,       # keeps its text, so only a sanity ceiling
    "infobox": 4000,   # ditto — becomes a key/value box
}
# A single "drop" selector must never take more than this share of the
# document's text with it. Noise is small; whatever is big is content.
DROP_MAX_SHARE = 0.25


def _too_big(tag, kind, total):
    """Does this mark cost more text than its block kind may swallow?"""
    limit = KIND_MAX_CHARS.get(kind)
    if limit is None:
        return False
    return len(tag.get_text(" ", strip=True)) > limit


def apply_to(soup, template, report=None):
    """Marks the page according to the template: noise is removed, the
    content-root selector supplies the new root, and each rule attaches its
    block kind as an attribute to the matched elements. build_page then only
    reads those marks off — so the existing heuristic stays as the safety
    net for everything unmarked.

    Everything that would cost content is refused here rather than trusted:
    oversized drops and marks over their kind's ceiling. `report` collects
    those refusals as text for preview()."""
    if not template:
        return soup
    # Fit check: if barely any of the template's own selectors find anything
    # here, it has nothing to say about this page and the heuristic takes
    # over. The template is NOT deleted — the next page will match it again.
    hits, total = coverage(soup, template)
    if total and hits < total * COVERAGE_MIN:
        if report is not None:
            report.append(
                f"Template not applied: only {hits} of {total} selectors "
                f"match this page.")
        return soup

    total = max(len(soup.get_text(" ", strip=True)), 1)
    for sel in template.get("drop") or []:
        try:
            hits = [tag for tag in soup.select(sel) if not tag.decomposed]
        except Exception:
            continue
        chars = sum(len(tag.get_text(" ", strip=True)) for tag in hits)
        if chars > total * DROP_MAX_SHARE:
            if report is not None:
                report.append(
                    f"drop {sel!r} refused: carries {chars} of {total} chars — "
                    f"that is content, not noise.")
            continue
        cuts = sum(len(tag.find_all("img")) for tag in hits)
        if cuts and report is not None:
            report.append(f"drop {sel!r} also takes {cuts} picture(s) off the page.")
        for tag in hits:
            if not tag.decomposed:
                tag.decompose()

    for rule in template.get("rules") or []:
        try:
            hits = soup.select(rule["sel"])
        except Exception:
            continue
        kind = rule["block"]
        for tag in hits:
            if tag.decomposed:
                continue
            if kind == "drop":
                chars = len(tag.get_text(" ", strip=True))
                if chars > total * DROP_MAX_SHARE:
                    if report is not None:
                        report.append(
                            f"drop rule {rule['sel']!r} refused: {chars} of "
                            f"{total} chars are content.")
                    continue
                tag.decompose()
                continue
            if _too_big(tag, kind, total):
                if report is not None:
                    report.append(
                        f"{kind} {rule['sel']!r} refused: element carries "
                        f"{len(tag.get_text(' ', strip=True))} chars, at most "
                        f"{KIND_MAX_CHARS[kind]} allowed — you hit a container, "
                        f"not a title.")
                continue
            tag[MARK_ATTR] = kind

    content = template.get("content")
    if content:
        try:
            root = soup.select_one(content)
        except Exception:
            root = None
        if root is not None and not root.decomposed and root.get_text(strip=True):
            return root
    return soup


# -- Fit check --------------------------------------------------------------


def text_size(page):
    """Text volume of a built page — the measure for "did it work"."""
    from .page import block_text
    return sum(len(block_text(b)) for b in page.blocks)


def images_lost(styled, plain):
    """How many of the baseline's pictures the template dropped. Counted on
    candidates, not on fetched art: the learning builds run without images,
    and a template that quietly clears the page of every picture must still
    fail its proof."""
    if styled is None or plain is None:
        return 0
    return max(getattr(plain, "image_candidates", 0)
               - getattr(styled, "image_candidates", 0), 0)


def check(styled, plain, min_ratio=0.6, max_image_loss=0.5):
    """Compares the templated page against the plain heuristic result. If
    the template loses more than 40% of the text, drops below 200
    characters, or throws away more than half of the pictures, it tore the
    page apart instead of styling it."""
    if styled is None:
        return False
    got = text_size(styled)
    if got < 200:
        return False
    pics = getattr(plain, "image_candidates", 0) if plain is not None else 0
    if pics and images_lost(styled, plain) > pics * max_image_loss:
        return False
    ref = text_size(plain) if plain is not None else 0
    if ref < 200:
        return True   # the baseline itself is worthless — not a fair comparison
    return got >= ref * min_ratio


# -- Verification sample ----------------------------------------------------


def _same_domain_links(page, limit):
    """Up to `limit` further URLs of the same domain, taken from the page's
    own link list. Deliberately no crawler: what the page links to is what a
    caller would visit next, and that is exactly the material the template
    has to survive."""
    home = domain_of(page.url)
    seen, out = {page.url.rstrip("/")}, []
    for url, _label in getattr(page, "links", []) or []:
        if domain_of(url) != home:
            continue
        key = url.rstrip("/")
        if key in seen or "#" in url:
            continue
        seen.add(key)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def fetch_html(url, firecrawl_cfg=None):
    """A verification page's document — over the same line the browser
    itself dials with (Firecrawl, else Playwright, else plain HTTP). On a
    JS-heavy site the bare HTTP document is a husk; selectors learned
    against that husk would never match what actually reaches the screen."""
    from .fetch import fetch_source
    try:
        return fetch_source(url, firecrawl_cfg)
    except Exception:
        return "", ""


class Sample:
    """One page the draft is measured against: raw HTML, its own soup for
    selector probing, and the plain heuristic build as baseline."""

    def __init__(self, url, html, plain):
        self.url = url
        self.html = html
        self.plain = plain
        self.soup = BeautifulSoup(html, "html.parser")


def collect_samples(page, build_plain, limit=VERIFY_LINKS, log=None,
                    firecrawl_cfg=None):
    """The page the user is on plus up to `limit` further pages of the same
    domain. Failing fetches are simply left out — a template verified on two
    pages is still worth more than one verified on none."""
    # Page 1's baseline is rebuilt too, instead of reusing the page on
    # screen: that one may carry images, and a draft measured against an
    # image-laden baseline would be judged unfairly.
    samples = [Sample(page.url, page.html, build_plain(page.html, page.url) or page)]
    for url in _same_domain_links(page, limit):
        html, final = fetch_html(url, firecrawl_cfg)
        if not html:
            continue
        plain = build_plain(html, final or url)
        if plain is None:
            continue
        samples.append(Sample(final or url, html, plain))
        if log:
            log(final or url)
    return samples


# -- Toolbox for the learning loop ------------------------------------------


PROBE_SAMPLE = 160     # characters of text sample per hit
PROBE_HITS = 3         # how many hits are shown individually
PREVIEW_BLOCKS = 20


class Toolbox:
    """The three tools the AI takes the site apart with.

    Everything here is measured across ALL samples, not just the page the
    user happens to stand on: `probe` reports hit counts per page (a
    selector matching only the start page is not a template), `preview`
    builds every sample and reports each one's text balance. That is the
    difference to the old single-page profiler — an overfitted draft cannot
    pass here.

    Built on its own soup copies: the tools may experiment without damaging
    the document that gets rendered later."""

    def __init__(self, samples, build):
        self.samples = samples
        self._build = build       # callable(html, url, template) -> page or None
        self.soup = samples[0].soup
        self.best = None          # best draft measured so far
        self._best_score = (-1, -1)   # (pages passed, text volume)

    # -- probing ---------------------------------------------------------

    def probe(self, selector):
        """What does this selector match — on every sample page? Hit count,
        tag, text volume, text sample. This is the question most mistakes
        hinge on: is this a title or half a screen of content?"""
        if not _valid_selector(self.soup, selector):
            return f"BAD SELECTOR: {selector}"
        lines = [f"TYPE SPEC {selector}"]
        for i, sample in enumerate(self.samples):
            hits = sample.soup.select(selector)
            lines.append(f"  GALLEY {i + 1} ({sample.url}): {len(hits)} HITS")
            if i:      # detail only for the main page, counts for the rest
                continue
            for tag in hits[:PROBE_HITS]:
                text = tag.get_text(" ", strip=True)
                kids = [c.name for c in tag.find_all(True, recursive=False)][:6]
                lines.append(
                    f"    <{tag.name}> {len(text)} CHARS, "
                    f"CHILDREN: {', '.join(kids) or '-'}\n"
                    f"    COPY: {text[:PROBE_SAMPLE]!r}"
                )
            if len(hits) > PROBE_HITS:
                lines.append(f"    ... {len(hits) - PROBE_HITS} MORE")
        return "\n".join(lines)

    def outline(self, selector=""):
        """Blueprint of the page or a subtree — tags with classes/IDs and
        the text volume below, without the text. This way the whole page
        doesn't have to go into the prompt upfront; the AI digs in where it
        is interested."""
        node = self.soup
        if selector:
            if not _valid_selector(self.soup, selector):
                return f"BAD SELECTOR: {selector}"
            node = self.soup.select_one(selector)
            if node is None:
                return f"NO HIT ON GALLEY 1: {selector}"
        return outline(node) or "(EMPTY)"

    # -- preview ---------------------------------------------------------

    def preview(self, template):
        """Runs the draft on EVERY sample page and reports back. A draft
        counts as passed only if it survives all of them — that is the whole
        point of the verification links."""
        clean = sanitize(template, self.soup)
        if clean is None:
            return ("PROOF REJECTED: no valid selector, no usable rule. "
                    "Check your selectors with the type spec first.")
        lines, passed, total_text = [], 0, 0
        for i, sample in enumerate(self.samples):
            # The same refusals the live browser applies — so a mark that
            # would swallow body copy shows up here, not only in the numbers.
            refused = []
            apply_to(BeautifulSoup(sample.html, "html.parser"), clean, refused)
            built = self._build(sample.html, sample.url, clean)
            if built is None:
                lines.append(f"  GALLEY {i + 1} ({sample.url}): WOULD NOT SET.")
                continue
            got, ref = text_size(built), text_size(sample.plain)
            ok = check(built, sample.plain)
            passed += bool(ok)
            total_text += got
            pics_ref = getattr(sample.plain, "image_candidates", 0)
            pics_got = pics_ref - images_lost(built, sample.plain)
            lines.append(
                f"  GALLEY {i + 1} ({sample.url}): {got} CHARS SET, "
                f"{ref} IN THE COPY, {pics_got}/{pics_ref} CUTS KEPT — "
                f"{'PASSED' if ok else 'SHORT, COPY OR CUTS LOST'}"
            )
            for note in refused[:6]:
                lines.append(f"    REFUSED: {note}")
            if i == 0:
                lines.append("  GALLEY 1, BLOCK BY BLOCK:")
                for block in built.blocks[:PREVIEW_BLOCKS]:
                    content = block.get("content", "")
                    lines.append(f"    {block.get('type')}: {content[:70]!r}")
                if len(built.blocks) > PREVIEW_BLOCKS:
                    lines.append(f"    ... {len(built.blocks) - PREVIEW_BLOCKS} MORE")

        # The best draft is the one passing on most pages; text volume only
        # breaks ties. Stored even when not every page passes, so a partly
        # working template beats none at all.
        score = (passed, total_text)
        if passed and score > self._best_score:
            self._best_score = score
            self.best = clean
        lines.insert(0, f"PROOF RUN: {passed}/{len(self.samples)} GALLEYS PASSED")
        if passed == len(self.samples):
            lines.append("ALL GALLEYS PASSED — THE TEMPLATE CAN GO TO PRESS.")
        else:
            lines.append("NOT EVERY GALLEY PASSED. FIX THE SELECTORS AND PROOF AGAIN.")
        return "\n".join(lines)

    @property
    def verified(self):
        """How many sample pages the best draft survived."""
        return max(self._best_score[0], 0)


# -- Storage ----------------------------------------------------------------


def load(url_or_domain):
    """The stored template for a URL or domain."""
    domain = domain_of(url_or_domain) if "://" in (url_or_domain or "") else url_or_domain
    if not domain:
        return None
    row = db.template_get(domain)
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except (ValueError, TypeError):
        db.template_delete(domain)
        return None
    return data if isinstance(data, dict) else None


def save(domain, model, template, verified=0):
    # The DB's `skeleton` column is a leftover of the old fingerprint fit
    # check and is no longer written; the column stays so existing databases
    # keep working unchanged.
    db.template_put(domain, model, "", json.dumps(template), verified)


def delete(domain):
    db.template_delete(domain)


def domains():
    return db.templates()


def exists(url_or_domain):
    domain = domain_of(url_or_domain) if "://" in (url_or_domain or "") else url_or_domain
    return bool(domain) and db.template_get(domain) is not None


def eligible(page):
    """Only real HTML pages of a real domain. Search result lists, Gopher/
    Gemini and Firecrawl markdown pages carry no document to hang selectors
    on."""
    if not page or getattr(page, "is_search", False):
        return False
    if not domain_of(page.url):
        return False
    return bool(getattr(page, "html", ""))
