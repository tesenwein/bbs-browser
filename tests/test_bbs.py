import json
import os
import re
import tempfile

# Point to a throwaway database BEFORE any module is loaded —
# a test run must not touch the caller's real mailbox.
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="bbs-test-"), "test.db")
os.environ["BBS_DB_FILE"] = _TEST_DB

from bbs_browser.page import build_page, find_logos, resolve_ddg
from bbs_browser.render import layout_page, RAW
from bbs_browser.images import halfblock_lines, render_image, render_logo, worth_fetching
from bbs_browser.constants import AMBER

html = """
<html><head><title>Test-Seite</title></head><body>
<nav><a href="/nav">NavLink</a></nav>
<div role="navigation"><a href="/rolenav">RoleNav</a></div>
<div aria-hidden="true"><p>Unsichtbar</p></div>
<main>
  <h1>Hallo Welt</h1>
  <p>Ein Absatz mit einem <a href="/foo">Foo-Link</a> und einem
     <a href="https://example.com/bar" aria-label="Bar via Aria"><img src="x.png"></a>.</p>
  <p><a href="/icon-only"><img src="logo.png"></a></p>
  <p>Nochmal <a href="/foo">Foo-Link</a> (gleiche URL, gleiche Nummer).</p>
""" + "".join(f"<p>Langer Absatz Nummer {i} mit ordentlich viel Text, damit der Renderer genug Text fuer das Layout hat.</p>" for i in range(8)) + """
  <pre>  preformatiert  </pre>
  <ul><li>Punkt eins <a href="/baz">Baz</a></li></ul>
</main>
<footer><a href="/foot">Footer</a></footer>
</body></html>
"""

page = build_page(html, "https://test.de", render_images=False)
assert page.title == "Test-Seite"
assert page.link_url(1) == "https://test.de/foo"
assert not any("NavLink" in l for _, l in page.links)
assert not any("Unsichtbar" in b.get("content", "") for b in page.blocks)
assert any(l == "Bar via Aria" for _, l in page.links)
for b in page.blocks:
    if b["type"] == "text":
        assert re.sub(r"\[\d+\]", "", b["content"]).strip(" .,|-·"), f"leerer Marker-Block: {b}"
assert any(b.get("content", "").startswith("· ") for b in page.blocks)
urls = [u for u, _ in page.links]
assert len(urls) == len(set(urls))

assert resolve_ddg("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fheise.de%2Fnews&x=1") == "https://heise.de/news"

# Link WRAPPING the block (<a><h2>...</h2></a>): headline gets a marker
news_html = """
<html><head><title>News</title></head><body><main>
  <a href="/artikel/1"><article><h2>Grosse Schlagzeile</h2><p>Teaser-Text zur Schlagzeile mit genug Inhalt.</p></article></a>
  <a href="/artikel/2"><h3>Zweite Schlagzeile</h3></a>
</main></body></html>
"""
news_page = build_page(news_html, "https://news.de", render_images=False)
headline = next(b for b in news_page.blocks if b["content"].startswith("Grosse Schlagzeile"))
assert re.search(r"\[\d+\]$", headline["content"]), f"Schlagzeile ohne Marker: {headline}"
assert news_page.link_url(1) == "https://news.de/artikel/1"
teaser = next(b for b in news_page.blocks if b["content"].startswith("Teaser-Text"))
assert teaser["content"].endswith("[1]")  # same URL -> same number
second = next(b for b in news_page.blocks if b["content"].startswith("Zweite Schlagzeile"))
assert second["content"].endswith("[2]")

# --- Parser without AI: what the browser extracts from raw HTML --------------
_pad = "<p>" + "Fuelltext damit die Seite nicht als zu duenn gilt. " * 8 + "</p>"


def _texts(body, url="https://t.de"):
    p = build_page(f"<html><title>T</title><body><main>{body}{_pad}</main></body></html>", url, render_images=False)
    return [b.get("content", "") for b in p.blocks]


# <noscript> is visible to us — we are the browser without JavaScript
assert any("Nur ohne JS" in x for x in _texts("<noscript><p>Nur ohne JS sichtbar</p></noscript>"))

# JSON-LD saves pages that only ship their text inside a script
_ld = build_page("""<html><head><title>T</title>
<script type="application/ld+json">{"@type":"NewsArticle","headline":"Die Schlagzeile",
"articleBody":"Erster Absatz.\\nZweiter Absatz mit mehr Text."}</script></head>
<body><main><div>x</div></main></body></html>""", "https://t.de", render_images=False)
assert any(b["type"] == "heading" and b["content"] == "Die Schlagzeile" for b in _ld.blocks)
assert any("Zweiter Absatz" in b.get("content", "") for b in _ld.blocks)

# <article> as content root when there is no <main>
_art = build_page(f"<html><title>T</title><body><div><p>Sidebar-Muell</p></div><article><h1>Titel</h1>{_pad}</article></body></html>", "https://t.de", render_images=False)
assert not any("Sidebar-Muell" in b.get("content", "") for b in _art.blocks)

# Readability scorer: without <main> and without <article>, the container with
# the most flowing text wins; the link-heavy column next to it drops out.
_nav_col = "<div><ul>" + "".join(f'<li><a href="/x{i}">Menuepunkt {i}</a></li>' for i in range(30)) + "</ul></div>"
_story = "<div>" + "".join(
    f"<p>Absatz {i}, mit Kommas, und genug Text, damit der Scorer ihn als Fliesstext wertet.</p>"
    for i in range(8)) + "</div>"
_read = build_page(f"<html><title>T</title><body><div>{_nav_col}{_story}</div></body></html>",
                   "https://t.de", render_images=False)
assert any("Absatz 7" in b.get("content", "") for b in _read.blocks)
assert not any("Menuepunkt" in b.get("content", "") for b in _read.blocks)

# ... but only if a candidate is truly convincing — otherwise everything stays.
_short = build_page("<html><title>T</title><body><div><p>Kurz, aber alles.</p></div></body></html>",
                    "https://t.de", render_images=False)
assert any("Kurz, aber alles." in b.get("content", "") for b in _short.blocks)

# <br> breaks into its own lines; hidden/display:none get dropped
assert {"Zeile eins", "Zeile zwei"} <= set(_texts("<p>Zeile eins<br>Zeile zwei</p>"))
assert not any("Versteckt" in x for x in _texts('<p hidden>Versteckt A</p><p style="display:none">Versteckt B</p>'))

# ol numbers, blockquote quotes, hr separates, emphasis is marked
_t = _texts("<ol><li>Erstens</li><li>Zweitens</li></ol><blockquote><p>Zitiert</p></blockquote><hr>"
            "<p>Ein <strong>wichtiges</strong> und <em>betontes</em> Wort im Satz.</p>")
assert "1. Erstens" in _t and "2. Zweitens" in _t
assert any(x.startswith("> ") and "Zitiert" in x for x in _t)
assert any(set(x) == {"─"} for x in _t)
assert any("*wichtiges*" in x and "/betontes/" in x for x in _t)

# Image URL also from lazy-load attributes and srcset
from bbs_browser.page import img_src
from bs4 import BeautifulSoup as _BS
_imgs = _BS('<img data-lazy-src="/a.jpg"><img srcset="/b-400.jpg 400w, /b-800.jpg 800w">', "html.parser").find_all("img")
assert img_src(_imgs[0]) == "/a.jpg" and img_src(_imgs[1]) == "/b-400.jpg"

# Meta refresh is recognized as a redirect target
assert build_page('<html><head><title>T</title><meta http-equiv="refresh" content="0; url=/neu"></head><body></body></html>',
                  "https://t.de", render_images=False).refresh_url == "https://t.de/neu"

# Data table -> ASCII frame with a separated header row
_tb = build_page(f"""<html><title>T</title><body><main><table>
<tr><th>Name</th><th>Jahr</th></tr><tr><td>Commodore 64</td><td>1982</td></tr>
<tr><td>Amiga 500</td><td>1987</td></tr></table>{_pad}</main></body></html>""", "https://t.de", render_images=False)
_frame = next(b for b in _tb.blocks if b["type"] == "table")
assert _frame["lines"][0].startswith("┌") and _frame["lines"][-1].startswith("└")
assert any("╞" in l for l in _frame["lines"]), "Kopfzeile nicht abgetrennt"
assert any("Commodore 64" in l for l in _frame["lines"])
assert not any(b["type"] == "text" and b["content"].strip() == "1982" for b in _tb.blocks), "Zellen doppelt"

# Layout tables (nested/ragged) stay as flowing text, without duplicate markers
_lay = build_page(f"""<html><title>T</title><body><main><table><tr><td>
<table><tr><td><a href="/x">Link X</a></td><td><a href="/y">Link Y</a></td></tr>
<tr><td>A</td><td>B</td></tr></table></td><td>Rechts</td></tr>
<tr><td>Nur eine Zelle</td></tr></table>{_pad}</main></body></html>""", "https://t.de", render_images=False)
assert not any(b["type"] == "table" for b in _lay.blocks), "Layout-Tabelle faelschlich gerahmt"
_all = " ".join(b.get("content", "") for b in _lay.blocks)
assert not re.search(r"\[\d+\]\s*\[\d+\]", _all), f"doppelte Marker: {_all[:120]}"

# A table that's too wide falls back to flowing text
_wide_row = "<tr>" + "".join(f"<td>Spalte {i} mit reichlich Text drin</td>" for i in range(9)) + "</tr>"
assert not any(b["type"] == "table" for b in build_page(
    f"<html><title>T</title><body><main><table>{_wide_row}{_wide_row}</table>{_pad}</main></body></html>",
    "https://t.de", render_images=False).blocks)

# CSS grid: text-less tiles become visible as a box ...
_grid = build_page(f"""<html><title>T</title><body><main><div class="teaser-grid">
<div>Erste Kachel mit ordentlich Text</div><div>Zweite Kachel mit ordentlich Text</div>
<div>Dritte Kachel mit ordentlich Text</div></div>{_pad}</main></body></html>""", "https://t.de", render_images=False)
assert any(b["type"] == "table" and any("Erste Kachel" in l for l in b["lines"]) for b in _grid.blocks)
# ... while short navigation chips are not a grid
_nav = build_page(f"""<html><title>T</title><body><main><div class="card-grid">
<div>Eins</div><div>Zwei</div><div>Drei</div></div>{_pad}</main></body></html>""", "https://t.de", render_images=False)
assert not any(b["type"] == "table" for b in _nav.blocks), "Navigations-Chips faelschlich gerahmt"
# ... and grids of real headlines are left untouched
_hg = build_page(f"""<html><title>T</title><body><main><div class="card-grid">
<div><a href="/a"><h2>Schlagzeile A</h2></a></div><div><a href="/b"><h2>Schlagzeile B</h2></a></div>
<div><a href="/c"><h2>Schlagzeile C</h2></a></div></div>{_pad}</main></body></html>""", "https://t.de", render_images=False)
assert not any(b["type"] == "table" for b in _hg.blocks), "Schlagzeilen-Grid faelschlich gerahmt"
assert all(re.search(r"\[\d+\]$", b["content"]) for b in _hg.blocks if b["type"] == "heading")

# Table typesetting: frame dimmed, content in terminal color
from bbs_browser.render import _style_frame
from bbs_browser.constants import DIM
_styled = _style_frame(AMBER, "│ Zelle │")
assert _styled.startswith(DIM) and AMBER in _styled

# Download and SysOp context must not lose tables/images
from bbs_browser.page import block_text, page_text
assert block_text({"type": "text", "content": "x"}) == "x"
assert "Zelle" in block_text({"type": "table", "lines": ["│ Zelle │"]})
assert block_text({"type": "image", "lines": [], "alt": "Foto"})
assert "Commodore 64" in page_text(_tb), "Tabelle fehlt im Seitentext"

# One column, full width: no column separator ever runs through body copy.
lines = layout_page(page, AMBER)
assert lines
assert not any(ln[0] == RAW and " │ " in ln[1] for ln in lines), "Spaltentrenner im Satz"
assert any(ln[0] and ln[0] != RAW for ln in lines), "Ueberschrift fehlt"

# Image detection: what isn't worth showing?
assert not worth_fetching("/img/logo.png")
assert not worth_fetching("/tracking/pixel.gif")
assert not worth_fetching("/media/photo.jpg", attr_w="32", attr_h="32")
assert worth_fetching("/media/photo.jpg", "Pressefoto", "800", "600")
assert worth_fetching("/uploads/2026/artikelbild.jpg")

# Markdown (Firecrawl MCP) -> page with numbered links
from bbs_browser.page import page_from_markdown
md_page = page_from_markdown(
    "# Schlagzeile\n\nEin Text mit [einem Link](https://ziel.de/a) drin.\n\n- [Zweiter](https://ziel.de/b)\n",
    "https://quelle.de",
)
assert md_page.title == "Schlagzeile"
assert md_page.link_url(1) == "https://ziel.de/a"
assert any("[1]" in b.get("content", "") for b in md_page.blocks)

# AI design parser (fallback without rich): frame lines stay pre, headings recognized
# Normal (non-AI) pages also get their topmost title as a block poster
from bbs_browser.page import mark_big_title
_np = build_page(
    "<html><head><title>T</title></head><body><main>"
    "<h1>Startseite</h1><p>Text.</p><h2>Weiter</h2><p>Mehr.</p>"
    "</main></body></html>",
    "https://demo.de", render_images=False,
)
_nh = [b for b in _np.blocks if b["type"] == "heading"]
assert _nh and _nh[0].get("big") is True
assert all(not h.get("big") for h in _nh[1:])
# mark_big_title is idempotent and robust without headings
class _NoHead:
    blocks = [{"type": "text", "content": "nur text"}]
mark_big_title(_NoHead())

# Large block titles (bigtext)
from bbs_browser import bigtext
_bt = bigtext.render_block("Info", 76)
assert _bt and all(len(l) <= 76 for l in _bt) and any(bigtext.FILL in l for l in _bt)
# Umlauts are transliterated, not swallowed
assert bigtext._normalize("Über & Groß") == "UEBER & GROSS"
# A single title that's too wide falls back cleanly (None), doesn't hang
assert bigtext.render_block("Donaudampfschifffahrtsgesellschaft", 76) is None
for _w in (10, 20, 40, 76):
    _r = bigtext.render_block("Neueste Nachrichten Heute", _w)
    assert _r is None or all(len(l) <= _w for l in _r)
# Fallback block font without pyfiglet: every glyph exactly 5 lines, equal width
for _ch, _g in bigtext._GLYPHS.items():
    assert len(_g) == bigtext.HEIGHT, f"Glyphe {_ch!r} hat {len(_g)} Zeilen"
    assert len({len(r) for r in _g}) == 1, f"Glyphe {_ch!r} ungleiche Zeilenbreiten"
_builtin = bigtext._render_builtin(bigtext._normalize("Test"), 76)
assert _builtin and len(_builtin) == bigtext.HEIGHT
# Heading with big=True renders the block font into the page layout
class _BigPage:
    blocks = [{"type": "heading", "content": "Info", "big": True}]
_hlines = layout_page(_BigPage(), AMBER)
assert any(bigtext.FILL in ln[1] for ln in _hlines)

# AI markdown -> rich phosphor: attributes stay, colors get dropped,
# link markers [n] survive (otherwise navigation would break).
from bbs_browser import markdown as _md
from bbs_browser.constants import AMBER as _AMBER, RESET as _RESET
_lines = _md.render("# TITEL\n\nText **fett** mit Link [7].\n\n- Punkt", _AMBER)
_joined = "\n".join(_lines)
assert _lines and all(l.startswith(_AMBER) for l in _lines)   # every line tinted
assert "[7]" in _joined and "TITEL" in _joined                # marker + text preserved
assert "\033[1m" in _joined                                   # bold attribute set
assert "\033[38;5;" not in _joined.replace(_AMBER, "")        # no foreign rich colors
# Emoji are stripped directly in render() — so EVERY chat path (SysOp,
# caller chat, log replay) stays clean; punctuation pictograms
# are mapped to ASCII instead of deleted ("73!" stays "73!").
_emoji_joined = "\n".join(_md.render("Roger! 👍 73❗", _AMBER))
assert "👍" not in _emoji_joined and "❗" not in _emoji_joined
assert "73!" in _emoji_joined
assert _md.strip_emoji("hi 🙂 du") == "hi du"
# Images in a chat reply: split out of the markdown and typeset as character
# art (like on a page) instead of ending up as rich's link markup.
_segs = _md.split_images("Schau:\n\n![Mond](https://x/y.png)\n\nHuebsch.")
assert [s[0] for s in _segs] == ["text", "image", "text"]
assert _segs[1][1:] == ("Mond", "https://x/y.png")
assert _md.split_images("nur text") == [("text", "nur text")]
from bbs_browser.terminal import Terminal as _ImgTerminal
_shot = _ImgTerminal(fast=True)
_art = _shot._image_lines(lambda url, alt: {"lines": ["##..", "..##"]}, "https://x/y.png", "Mond")
assert "Mond" in _art[0] and "##.." in _art[1]
# Images off (callback returns nothing): the label remains, nothing crashes.
assert len(_shot._image_lines(lambda url, alt: None, "https://x/y.png", "Mond")) == 1
# md block passes through layout_page as RAW (already styled, no longer wrapped)
class _MdPage:
    blocks = [{"type": "md", "content": "# H\n\nAbsatz [2] hier."}]
_md_lines = layout_page(_MdPage(), _AMBER)
assert any(style == RAW and "[2]" in text for style, text in _md_lines)
# Pager keeps groups (images, titles) together — a page break never falls through them.
from bbs_browser.render import _split_pages
# Group taller than one page: still stays in one piece (its own page, runs
# over) instead of being cut apart by the MORE prompt.
_tall = [(RAW, f"img{_i}", "g1") for _i in range(10)]
_tp = _split_pages(_tall, per_page=4)
assert len(_tp) == 1 and len(_tp[0]) == 10, "Ueberlange Gruppe wurde zerschnitten"
# Group no longer fits on the started page -> break BEFORE it, complete.
_mixed = [(None, "a"), (None, "b")] + [(RAW, f"g{_i}", "gg") for _i in range(3)]
_mp = _split_pages(_mixed, per_page=4)
assert all(len(_l) == 2 for _l in _mp[0]), "Gruppenzeile auf die Vorseite gerutscht"
assert len(_mp[1]) == 3, "Gruppe nach dem Umbruch nicht vollstaendig"
# Simple lines still fill pages normally.
assert [len(_p) for _p in _split_pages([(None, str(_i)) for _i in range(9)], 4)] == [4, 4, 1]
from bbs_browser.i18n import t as _t, set_lang as _set_lang
_set_lang("de")

# -- SQLite storage: sections, chat history, migration ---------------------
import json as _json_db
from bbs_browser import db as _dbmod

_dbmod.set_section("probe", {"a": 1})
assert _dbmod.get_section("probe") == {"a": 1}
_dbmod.set_section("probe", {"a": 2})
assert _dbmod.get_section("probe") == {"a": 2}, "Sektion nicht ueberschrieben"
assert _dbmod.get_section("gibtsnicht") == {}

_dbmod.chat_clear("probe-kanal")
_dbmod.chat_append("probe-kanal", "user", "LANGER PROMPT MIT KONTEXT", display="kurz")
_dbmod.chat_append("probe-kanal", "assistant", "antwort")
assert _dbmod.chat_history("probe-kanal") == [
    {"role": "user", "content": "LANGER PROMPT MIT KONTEXT"},
    {"role": "assistant", "content": "antwort"},
], "Verlauf fuer die KI falsch"
_script = _dbmod.chat_transcript("probe-kanal")
assert [l["text"] for l in _script] == ["kurz", "antwort"], "Anzeige nutzt display nicht"
assert any(c["channel"] == "probe-kanal" and c["count"] == 2 for c in _dbmod.chat_channels())
_dbmod.chat_clear("probe-kanal")
assert _dbmod.chat_history("probe-kanal") == []

# Migration: old JSON files migrate once into a fresh DB
_mig_dir = tempfile.mkdtemp(prefix="bbs-mig-")
_old_state = os.path.join(_mig_dir, "state.json")
with open(_old_state, "w") as _f:
    _json_db.dump({
        "bookmarks": ["https://a.de"],
        "history": ["https://b.de"],
        "ui": {"width": 100},
        "users": {"pool": [{"handle": "ZOKK"}], "chats": {"ZOKK": [
            {"role": "user", "content": "alt"}, {"role": "assistant", "content": "auch alt"},
        ]}},
    }, _f)
_prev = (_dbmod.LEGACY_STATE_FILE, os.environ["BBS_DB_FILE"])
_dbmod.LEGACY_STATE_FILE = _old_state
os.environ["BBS_DB_FILE"] = os.path.join(_mig_dir, "neu.db")
_dbmod.close()
assert _dbmod.get_section("nav") == {"bookmarks": ["https://a.de"], "history": ["https://b.de"]}, \
    "Bookmarks/Verlauf nicht in die nav-Sektion gewandert"
assert _dbmod.get_section("ui") == {"width": 100}
assert "chats" not in _dbmod.get_section("users"), "Chats haetten aus der Sektion verschwinden muessen"
assert [l["text"] for l in _dbmod.chat_transcript("user:ZOKK")] == ["alt", "auch alt"], \
    "Alte Privatchats nicht uebernommen"
# A second connection setup must not import again
_dbmod.set_section("nav", {"bookmarks": [], "history": []})
_dbmod.close()
assert _dbmod.get_section("nav") == {"bookmarks": [], "history": []}, "Migration lief ein zweites Mal"

_dbmod.LEGACY_STATE_FILE, os.environ["BBS_DB_FILE"] = _prev
_dbmod.close()

# Chat log display: runs through even when nothing is stored
from bbs_browser import chatlog as _chatlog
from bbs_browser.terminal import Terminal as _ChatlogTerminal
_chatlog_term = _ChatlogTerminal(fast=True)
_dbmod.chat_clear()
_chatlog.run(_chatlog_term)                      # "nothing saved yet"
_dbmod.chat_append("sysop", "user", "frage")
_dbmod.chat_append("sysop", "assistant", "antwort")
_chatlog.run(_chatlog_term)                      # list
_chatlog.run(_chatlog_term, "1")                 # read history
_chatlog.run(_chatlog_term, "99")                # invalid number
_chatlog.run(_chatlog_term, "del 1")
assert _dbmod.chat_history("sysop") == [], "'log del' hat nicht geloescht"

# 'chat <nr>' re-enters a history via the list number
class _ResumeSysop:
    def __init__(self):
        self.calls = 0
    def chat(self):
        self.calls += 1

class _ResumeUsers:
    def __init__(self):
        self.handles = []
    def resume_chat(self, handle):
        self.handles.append(handle)

class _ResumeBrowser:
    pass

_rb = _ResumeBrowser()
_rb.sysop = _ResumeSysop()
_rb.users = _ResumeUsers()
_chatlog.resume_by_number(_chatlog_term, _rb, "1")   # nothing saved yet
assert _rb.sysop.calls == 0
_dbmod.chat_append("user:ZOKK", "user", "hi")
_dbmod.chat_append("sysop", "user", "frage")         # newest channel -> No. 1
_chatlog.resume_by_number(_chatlog_term, _rb, "1")
assert _rb.sysop.calls == 1, "'chat 1' hat den SysOp-Chat nicht fortgesetzt"
_chatlog.resume_by_number(_chatlog_term, _rb, "2")
assert _rb.users.handles == ["ZOKK"], "'chat 2' hat den Privatchat nicht fortgesetzt"
_chatlog.resume_by_number(_chatlog_term, _rb, "99")  # invalid number -> just an error message
assert _rb.sysop.calls == 1 and _rb.users.handles == ["ZOKK"]
_dbmod.chat_clear()

# Config menu / state / navigation importable
from bbs_browser.configmenu import config_menu, run_firecrawl_check
from bbs_browser.navigation import command_loop
from bbs_browser.state import load_section

# Smart color mode
from bbs_browser.colors import pick_color, PHOSPHORS
name, ansi = pick_color("#e3000f", "heise.de")   # heise red -> ROT
assert name == "ROT" and ansi.startswith("\033[")
name, _ = pick_color("#1db954", "spotify.com")   # Spotify green
assert name == "GRUEN"
assert pick_color("#111111", "x.de") == pick_color("", "x.de")  # too dark -> domain hash
assert pick_color("", "x.de") == pick_color("", "www.x.de")     # stable, www doesn't matter
assert pick_color("", "x.de")[1] in [p[1] for p in PHOSPHORS]

# theme-color is read from the <head>
tc_page = build_page('<html><head><title>T</title><meta name="theme-color" content="#e3000f"></head><body><main><p>Hallo Welt, genug Text.</p></main></body></html>', "https://t.de", render_images=False)
assert tc_page.theme_color == "#e3000f"

# Firecrawl check (offline cases only: no key, no host -> no network)
import os
from bbs_browser.page import firecrawl_check
os.environ.pop("FIRECRAWL_API_KEY", None)

res = firecrawl_check({}, "")
assert ("WARN", "Firecrawl ist AUS (Menue 'c' -> 4)") in res
assert any(s == "FEHLER" and "API-Key" in m for s, m in res)

res = firecrawl_check({"enabled": True, "use_mcp": True}, "vck_abc")
assert any(s == "FEHLER" and "vck_" in m for s, m in res)
assert any(s == "FEHLER" and "fc-Key" in m for s, m in res)

res = firecrawl_check({"enabled": True, "use_mcp": True, "api_key": "fc-x"}, "sk-ant-x")
assert any(s == "OK" and "MCP-tauglich" in m for s, m in res)
assert not any(s == "FEHLER" for s, m in res)

# Gopher menu -> page with numbered links
from bbs_browser.retronet import parse_gopher_menu, parse_gemtext, _gemini_join
gmenu = "iWillkommen bei Floodgap\t\terror.host\t1\n1Nachrichten\t/news\tgopher.floodgap.com\t70\n0Über uns\t/about.txt\tgopher.floodgap.com\t70\nhHomepage\tURL:https://floodgap.com\tgopher.floodgap.com\t70\n."
gp = parse_gopher_menu(gmenu, "gopher://gopher.floodgap.com/")
assert gp.link_url(1) == "gopher://gopher.floodgap.com/1/news"
assert gp.link_url(3) == "https://floodgap.com"
assert any(b["content"] == "Willkommen bei Floodgap" for b in gp.blocks)

# Gemtext -> page with numbered links
gt = parse_gemtext("# Startseite\n=> /docs Doku lesen\n=> gemini://andere.host/ Anderswo\n```\nASCII ART\n```\n* Punkt", "gemini://beispiel.de/")
assert gt.title == "Startseite"
assert gt.link_url(1) == "gemini://beispiel.de/docs"
assert gt.link_url(2) == "gemini://andere.host/"
assert any(b["type"] == "pre" and b["content"] == "ASCII ART" for b in gt.blocks)
assert _gemini_join("gemini://a.de/x/y", "../z") == "gemini://a.de/z"

# RSS -> Message Base
from bbs_browser.feeds import parse_feed
rss = b"<rss><channel><title>Test-Feed</title><item><title>Erster Beitrag</title><link>https://t.de/1</link><description>&lt;p&gt;Text&lt;/p&gt;</description></item></channel></rss>"
fp = parse_feed(rss, "https://t.de/feed")
assert fp.title == "Test-Feed"
assert fp.link_url(1) == "https://t.de/1"
assert any("Erster Beitrag[1]" in b.get("content", "") for b in fp.blocks)

# Feed detection in <head>
feed_page = build_page('<html><head><title>T</title><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head><body><main><p>Hallo Welt, genug Text hier.</p></main></body></html>', "https://t.de", render_images=False)
assert feed_page.feed_url == "https://t.de/feed.xml"

# -- Feeds: Datum aus beiden Dialekten ------------------------------------
from bbs_browser import feeds as _feeds

_rss_xml = b"""<?xml version="1.0"?><rss><channel><title>Quelle A</title>
<item><title>Alte Meldung aus dem Maerz</title><link>https://a.tld/1</link>
<pubDate>Tue, 03 Mar 2026 08:00:00 +0000</pubDate></item>
<item><title>Neue Meldung von heute frueh</title><link>https://a.tld/2</link>
<pubDate>Wed, 22 Jul 2026 06:00:00 +0000</pubDate></item>
</channel></rss>"""
_atom_xml = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<title>Quelle B</title>
<entry><title>Mittlere Meldung von gestern</title><link href="https://b.tld/1"/>
<updated>2026-07-21T12:00:00Z</updated></entry>
<entry><title>Meldung ganz ohne Datum</title><link href="https://b.tld/2"/></entry>
</feed>"""

_rss = _feeds.parse_feed(_rss_xml, "https://a.tld/feed")
_atom = _feeds.parse_feed(_atom_xml, "https://b.tld/feed")
assert [i["ts"] is not None for i in _rss.feed_items] == [True, True], "RSS-Datum nicht gelesen"
assert _atom.feed_items[0]["ts"] is not None, "Atom-Datum nicht gelesen"
assert _atom.feed_items[1]["ts"] is None, "Fehlendes Datum muss None bleiben"
# Ein Datum ohne Zone gilt als UTC, sonst driften Quellen gegeneinander.
assert _feeds.timestamp("2026-07-21T12:00:00") == _feeds.timestamp("2026-07-21T12:00:00Z")
assert _feeds.timestamp("kein datum") is None and _feeds.timestamp("") is None

# -- Newsdesk: die Normalisierungsschicht ---------------------------------
# Verschiedene Quellenarten muessen dieselbe Form annehmen, damit sie sich
# nach Datum mischen lassen.
from bbs_browser import newsdesk as _nd

assert _nd.normalize("https://a.tld/feed") == [{"url": "https://a.tld/feed", "enabled": True}], \
    "Alte Einzelquelle wurde nicht uebernommen"
assert _nd.normalize(["https://a.tld", "https://a.tld"]) == [{"url": "https://a.tld", "enabled": True}], \
    "Doppelte Quelle nicht entfernt"
assert _nd.normalize(None) == [] and _nd.normalize("") == []
assert _nd.enabled_urls([{"url": "https://a.tld", "enabled": False},
                         {"url": "https://b.tld", "enabled": True}]) == ["https://b.tld"]
assert _nd.label_for("https://www.srf.ch/news/feed") == "srf.ch"

_mixed = _nd.merge([
    {"text": "ohne Datum", "title": "ohne Datum", "url": "https://c.tld/x", "ts": None,
     "source": "c.tld", "kind": _nd.AI},
    {"text": "alt", "title": "alt", "url": "https://a.tld/1", "ts": 1000,
     "source": "a.tld", "kind": _nd.RSS},
    {"text": "neu", "title": "neu", "url": "https://b.tld/1", "ts": 9000,
     "source": "b.tld", "kind": _nd.RSS},
    {"text": "neu (Doppel)", "title": "neu", "url": "https://b.tld/1/", "ts": 8000,
     "source": "d.tld", "kind": _nd.RSS},
], 10)
assert [e["text"] for e in _mixed] == ["neu", "alt", "ohne Datum"], \
    f"Mischung nicht nach Datum sortiert: {[e['text'] for e in _mixed]}"
assert len(_mixed) == 3, "Dieselbe Meldung aus zwei Feeds wurde nicht entdoppelt"
assert len(_nd.merge(_mixed, 2)) == 2, "count wird nicht eingehalten"

# -- Bulletins: mehrere Quellen zu einem Board gemischt -------------------
from unittest import mock as _mk

from bbs_browser import bulletins as _bul
from bbs_browser import db as _db

# Altbestand: die frueher einzelne "url" wandert in die Quellenliste.
_db.set_section(_bul.SECTION, {"url": "https://alt.tld/feed", "ttl_hours": 6, "count": 5})
assert _bul.config()["sources"] == [{"url": "https://alt.tld/feed", "enabled": True}], \
    "Einzelquelle aus alter Konfiguration ging verloren"

_bul.save_config({"sources": ["https://a.tld/feed", "https://b.tld/feed"],
                  "ttl_hours": 6, "count": 5})
_bul.clear()
assert _bul.configured() and _bul.active_urls() == ["https://a.tld/feed", "https://b.tld/feed"]


def _fake_page_of(url):
    return (_rss if "a.tld" in url else _atom), True


with _mk.patch.object(_nd, "_page_of", _fake_page_of):
    _board = _bul.generate(None)          # ohne SysOp: reine Feeds kosten nichts

assert [e["text"] for e in _board] == [
    "Neue Meldung von heute frueh",       # 22.07. — beide Quellen gemischt
    "Mittlere Meldung von gestern",       # 21.07.
    "Alte Meldung aus dem Maerz",         # 03.03.
    "Meldung ganz ohne Datum",            # undatiert, deshalb ganz hinten
], f"Board nicht nach Datum gemischt: {[e['text'] for e in _board]}"
assert {e["source"] for e in _board} == {"a.tld", "b.tld"}, "Herkunft fehlt am Eintrag"
assert _bul.from_feed() and not _bul.needs_ai(), "Reines Feed-Board darf keinen Schluessel verlangen"
assert _bul.items() == _board, "Board wurde nicht zwischengespeichert"
assert _bul.entry_age(_board[0]), "Datierter Eintrag ohne Altersangabe"
assert _bul.entry_age(_board[-1]) == "", "Undatierter Eintrag darf kein Alter erfinden"

# Quellenliste geaendert -> der Cache beschreibt ein anderes Board und faellt weg.
_bul.save_config({"sources": ["https://a.tld/feed"], "ttl_hours": 6, "count": 5})
assert _bul.items() == [], "Cache ueberlebte eine geaenderte Quellenmischung"

# Eine abgeschaltete Quelle zaehlt nicht mehr mit.
_bul.save_config({"sources": [{"url": "https://a.tld/feed", "enabled": False}],
                  "ttl_hours": 6, "count": 5})
assert not _bul.configured(), "Abgeschaltete Quelle gilt weiter als gesetzt"
_db.set_section(_bul.SECTION, {})
_bul.clear()

# -- Konfigmenue: Quellenliste zeichnet sich ohne Terminal ----------------
# Das Menue selbst ist interaktiv, seine Zeilen sind es nicht: rows() baut
# jede Zeile aus i18n-Texten, ein fehlender Schluessel faellt hier auf.
from bbs_browser import configmenu as _cm

_db.set_section(_bul.SECTION, {"sources": [{"url": "https://a.tld/feed", "enabled": True},
                                           {"url": "https://b.tld/feed", "enabled": False}]})
_seen_rows = []


def _capture_menu(term, title, rows, **kw):
    _seen_rows.append(rows() if callable(rows) else rows)
    return ""            # wie ESC: sofort zurueck


with _mk.patch.object(_cm.lightbar, "menu", _capture_menu):
    _cm._bulletin_sources_menu(_mk.Mock(color=""))
_labels = [(r[0], r[2]) for r in _seen_rows[0]]

assert _labels[0] == ("1", _t("configmenu.on")), f"Aktive Quelle falsch angezeigt: {_labels}"
assert _labels[1] == ("2", _t("configmenu.off")), f"Stille Quelle falsch angezeigt: {_labels}"
assert _labels[-1][0] == "a", "Zeile zum Hinzufuegen fehlt"

# Bulletins haengen im Hauptmenue, nicht mehr unter dem KI-SysOp. Und jeder
# Punkt behaelt seine Ein-Tasten-Kurzwahl (Reset auf '0', nicht '10').
_menus = {}


def _capture_titled(term, title, rows, **kw):
    _menus[title] = rows() if callable(rows) else rows
    return ""


with _mk.patch.object(_cm.lightbar, "menu", _capture_titled):
    _cm.config_menu(_mk.Mock(color=""), _mk.Mock(), _mk.Mock())
    _cm._ai_menu(_mk.Mock(color=""), _mk.Mock(), _mk.Mock())
_main = _menus[_t("configmenu.title_main")]
_ai_rows = _menus[_t("configmenu.title_ai")]
assert any(r[1] == _t("configmenu.bulletins") for r in _main), "Bulletins fehlen im Hauptmenue"
assert not any(r[1] == _t("configmenu.bulletins") for r in _ai_rows), \
    "Bulletins haengen noch im KI-Menue"
assert all(len(r[0]) == 1 for r in _main if r[0]), \
    f"Mehrstellige Kurzwahl im Hauptmenue: {[r[0] for r in _main]}"
assert len({r[0] for r in _main}) == len(_main), "Doppelte Kurzwahl im Hauptmenue"

_db.set_section(_bul.SECTION, {})

# Jeder UI-Text existiert in beiden Sprachen (leer ist erlaubt: "Uhr" hat
# im Englischen keine Entsprechung, fehlend waere aber ein Loch im Menue).
from bbs_browser.i18n import ALL_STRINGS as _ALL

_luecken = [k for k, v in _ALL.items() if "de" not in v or "en" not in v]
assert not _luecken, f"Uebersetzung fehlt: {_luecken}"

# Startup sequence: modem chatter, welcome screen, bulletins
from bbs_browser.terminal import BANNER, DIAL_SEQUENCE, Terminal as _T
from bbs_browser.nostalgia import BULLETINS, WEEKDAYS, system_screen, version
assert "CONNECT" in " ".join(t for t, _, _ in DIAL_SEQUENCE)
assert any(kind == "dial" for _, _, kind in DIAL_SEQUENCE)
assert all(len(l) <= 80 for l in BANNER.splitlines()), "Banner passt nicht in 80 Spalten"
assert len(WEEKDAYS) == 7 and WEEKDAYS[0] == "Montag"
assert version()                                    # from the package metadata
for _n in range(len(BULLETINS) + 3):                # rotation without index errors
    assert BULLETINS[_n % len(BULLETINS)]
system_screen(_T(fast=True), {"handle": "TESTER", "caller_count": 3}, None)

# Nostalgia helpers
from bbs_browser.nostalgia import safe_filename
assert safe_filename("Heise News: Top-Meldung!") == "Heise_News_Top-Meldung.txt"
assert safe_filename("bild.jpg", ".jpg") == "bild.jpg"

# Gopher/Gemini dispatch importable, retro modules hang off fetch_page
from bbs_browser.page import fetch_page  # noqa: F811

# Firecrawl (SDK): build_page gets the RAW HTML so the logo AND page structure
# survive. Firecrawl's cleaned "html" format throws away <head>/<header> —
# building from that would lose the logo and structure. We mock the scrape and
# supply raw HTML with a header plus cleaned HTML without a header; the logo
# only appears in the raw one, which proves the raw HTML was used.
import bbs_browser.page as _pagemod
_fc_raw = (
    '<html><head><title>FC-Seite</title></head><body>'
    '<header><a href="https://fc.de/"><img src="/logo.png" alt="fc"></a></header>'
    '<main><h1>Echte Schlagzeile</h1>'
    + "".join(f"<p>Absatz {i} mit genug Text fuer den Renderer.</p>" for i in range(4))
    + '</main></body></html>'
)
# The cleaned HTML deliberately carries ONLY a stub paragraph, the raw one the
# real paragraphs. So the page content is the proof of which HTML was built.
_fc_clean = '<main><h1>Echte Schlagzeile</h1><p>Nur der bereinigte Rumpf.</p></main>'
_fc_orig = _pagemod.firecrawl_scrape
_pagemod.firecrawl_scrape = lambda url, api_key, base: (_fc_clean, "", _fc_raw, None)
try:
    _fc_page, _fc_err = _pagemod.fetch_page(
        "https://fc.de/artikel", {"enabled": True, "api_key": "fc-test"}, render_images=False,
    )
finally:
    _pagemod.firecrawl_scrape = _fc_orig
_fc_text = " ".join(b.get("content", "") for b in _fc_page.blocks)
assert _fc_err is None
assert _fc_page.logo_urls and any("logo.png" in u for u in _fc_page.logo_urls), \
    "Firecrawl: Logo aus dem <header> des rohen HTML fehlt"
assert any(b.get("content") == "Echte Schlagzeile" for b in _fc_page.blocks), \
    "Firecrawl: Seitenaufbau (Ueberschrift) fehlt"
assert "Absatz 0 mit genug Text" in _fc_text, \
    "Firecrawl: rohes HTML wurde nicht als Seiteninhalt verwendet"
assert "bereinigte Rumpf" not in _fc_text, \
    "Firecrawl: bereinigtes HTML wurde faelschlich statt des rohen gebaut"

# Firecrawl ACTIVE, scrape fails: Playwright stays out of it — it proceeds
# directly via HTTP, and the Firecrawl error hangs off the page.
# Previously local Chromium silently jumped in here, and the user took
# its result for Firecrawl's work.
from bbs_browser import jsrender as _jsmod

class _HttpResp:
    status_code = 200
    url = "https://fc.de/artikel"
    headers = {"Content-Type": "text/html; charset=utf-8"}
    text = ('<html><head><title>HTTP</title></head><body><main>'
            + "<p>HTTP-Absatz mit ordentlich Text fuer den Renderer.</p>" * 10
            + '</main></body></html>')
    def raise_for_status(self):
        pass

_js_calls = []
_av_orig, _rd_orig = _jsmod.available, _jsmod.render
_jsmod.available = lambda: True
_jsmod.render = lambda url, timeout=20000: (
    _js_calls.append(url),
    ('<html><body><main><p>Playwright-Seite</p></main></body></html>', url),
)[1]
_rq_orig = _pagemod.requests.get
_pagemod.requests.get = lambda *a, **kw: _HttpResp()
_pagemod.firecrawl_scrape = lambda url, api_key, base: ("", "", "", "Credits aufgebraucht")
try:
    _fcp, _fce = _pagemod.fetch_page(
        "https://fc.de/artikel", {"enabled": True, "api_key": "fc-test"}, render_images=False,
    )
finally:
    _pagemod.firecrawl_scrape = _fc_orig
    _pagemod.requests.get = _rq_orig
    _jsmod.available, _jsmod.render = _av_orig, _rd_orig
assert _fce is None
assert not _js_calls, "Firecrawl aktiv: Playwright darf nicht anspringen"
assert _fcp.firecrawl_error == "Credits aufgebraucht", "Firecrawl-Fehler muss an der Seite haengen"
assert "HTTP-Absatz" in " ".join(b.get("content", "") for b in _fcp.blocks), \
    "Firecrawl-Fehler: der Ersatz muss der nackte HTTP-Abruf sein"

# Firecrawl kaputt: nach genug Fehlschlaegen wird es fuer die Sitzung ignoriert —
# dann darf Playwright wieder ran, und der SDK-Aufruf faellt ganz weg.
_pagemod.firecrawl_reset()
_fc_calls = []
_pagemod.firecrawl_scrape = lambda url, api_key, base: (
    _fc_calls.append(url), ("", "", "", "Host nicht erreichbar"))[1]
_jsmod.available, _jsmod.render = lambda: True, lambda url: (
    '<html><body><main><p>Playwright-Seite</p></main></body></html>', url)
_pagemod.requests.get = lambda *a, **kw: _HttpResp()
try:
    _fccfg = {"enabled": True, "api_key": "fc-test"}
    for _ in range(_pagemod.FIRECRAWL_MAX_FAILURES):
        _pagemod.fetch_page("https://fc.de/a", _fccfg, render_images=False)
    assert _pagemod.firecrawl_muted(), "nach wiederholten Fehlern muss Firecrawl stummgeschaltet sein"
    _n_before = len(_fc_calls)
    _mp, _ = _pagemod.fetch_page("https://fc.de/b", _fccfg, render_images=False)
    assert len(_fc_calls) == _n_before, "stummgeschaltet: Firecrawl darf nicht mehr aufgerufen werden"
    assert not _mp.firecrawl_error, "stummgeschaltet: kein weiterer Firecrawl-Fehler mehr"
    assert "Playwright-Seite" in " ".join(b.get("content", "") for b in _mp.blocks), \
        "stummgeschaltet: der normale JS-Pfad muss uebernehmen"
    _pagemod.firecrawl_reset()
    assert not _pagemod.firecrawl_muted(), "firecrawl_reset muss den Schalter loesen"
finally:
    _pagemod.firecrawl_scrape = _fc_orig
    _pagemod.requests.get = _rq_orig
    _jsmod.available, _jsmod.render = _av_orig, _rd_orig
    _pagemod.firecrawl_reset()

# Firecrawl OFF: Playwright is still the JS path.
_jsmod.available = lambda: True
_jsmod.render = lambda url, timeout=20000: (
    '<html><head><title>JS</title></head><body><main>'
    + "<p>JS-Absatz mit ordentlich Text fuer den Renderer.</p>" * 10
    + '</main></body></html>', url)
try:
    _jsp, _jse = _pagemod.fetch_page("https://js.de/", {}, render_images=False)
finally:
    _jsmod.available, _jsmod.render = _av_orig, _rd_orig
assert _jse is None and "JS-Absatz" in " ".join(b.get("content", "") for b in _jsp.blocks), \
    "Ohne Firecrawl muss Playwright rendern"

# The scrape must give Firecrawl time for the page's JS (waitFor also
# forces the browser engine — without it Firecrawl returns SPAs as an empty shell).
import sys as _sys, types as _types
_fc_captured = {}

class _FakeFcDoc:
    html = ""
    markdown = "ok"
    raw_html = "<html><body><p>x</p></body></html>"

class _FakeFirecrawl:
    def __init__(self, **kw):
        pass
    def scrape(self, url, formats=None, wait_for=None):
        _fc_captured["wait_for"] = wait_for
        return _FakeFcDoc()

_fc_fake_mod = _types.ModuleType("firecrawl")
_fc_fake_mod.Firecrawl = _FakeFirecrawl
_fc_mod_orig = _sys.modules.get("firecrawl")
_sys.modules["firecrawl"] = _fc_fake_mod
try:
    _, _md, _raw, _err = _pagemod.firecrawl_scrape("https://x.de/", "fc-k", "")
finally:
    if _fc_mod_orig is not None:
        _sys.modules["firecrawl"] = _fc_mod_orig
    else:
        _sys.modules.pop("firecrawl", None)
assert _err is None and _md == "ok" and _raw
assert _fc_captured["wait_for"] == _pagemod.FIRECRAWL_WAIT_MS > 0, \
    "Scrape ohne wait_for: Firecrawl rendert das Seiten-JS nicht zuverlaessig"

# Firecrawl search: hits from v2 (web) and v1 responses (data), object or dict
from bbs_browser.page import _search_results, page_from_search_results
assert _search_results({"web": [{"url": "https://a.de", "title": "A", "description": "d"}]}) \
    == [("https://a.de", "A", "d")]
assert _search_results({"data": [{"url": "https://b.de"}]}) == [("https://b.de", "https://b.de", "")]

class _FcItem:
    url = "https://obj.de"; title = "Objekt"; description = "Als Objekt"
class _FcData:
    web = [_FcItem()]
assert _search_results(_FcData()) == [("https://obj.de", "Objekt", "Als Objekt")]

# ... and as a BBS page with numbered links
_sp = page_from_search_results("nintendo", [("https://n.de", "Nintendo", "Konsole"), ("https://m.de", "Mario", "")])
assert _sp.link_url(1) == "https://n.de" and _sp.link_url(2) == "https://m.de"
assert any("Nintendo [1]" in b.get("content", "") for b in _sp.blocks)
assert any(b.get("content") == "Konsole" for b in _sp.blocks)

# SysOp tool im_netz_suchen: uses the Firecrawl search API instead of the DDG scrape
from bbs_browser.sysop import SysOp

class _FcBrowser:
    firecrawl = {"enabled": True, "api_key": "fc-test"}
    page = None

_so = SysOp(_T(fast=True), _FcBrowser())
_tools = {tl["name"]: tl["func"] for tl in _so._tool_registry()}
_fs_orig = _pagemod.firecrawl_search
_pagemod.firecrawl_search = lambda q, key, base, limit=8: ([("https://t.de", "Treffer", "Snippet")], None)
try:
    _out = _tools["im_netz_suchen"]("testsuche")
finally:
    _pagemod.firecrawl_search = _fs_orig
assert "[1] Treffer -> https://t.de" in _out and "Snippet" in _out

# If the search API AND DDG both fail, BOTH reasons show up in the tool result —
# previously the tool swallowed the error and just reported "No results".
_fp_orig = _pagemod.fetch_page
_pagemod.firecrawl_search = lambda q, key, base, limit=8: ([], "kein Credit")
_pagemod.fetch_page = lambda url, cfg=None, **kw: (None, "NO CARRIER")
try:
    _out = _tools["im_netz_suchen"]("testsuche")
finally:
    _pagemod.firecrawl_search = _fs_orig
    _pagemod.fetch_page = _fp_orig
assert "kein Credit" in _out and "NO CARRIER" in _out

# Manual as the single source of truth
from bbs_browser import manual
HELP = manual.overview()
# The overview comes as a box per category — frame and title must be present
assert "╔" in HELP and "┌─[ " in HELP
for _cat in ("NAVIGATION", "KI-SYSOP", "SPIELHALLE"):
    assert f"┌─[ {_cat} ]" in HELP, f"Kasten fuer '{_cat}' fehlt in der Hilfe"
assert all(len(_l) <= 100 for _l in HELP.splitlines()), "Hilfe-Kasten laeuft zu breit"
for q in ("rss", "l", "/", "baud", "Firecrawl", "chat"):
    assert manual.lookup(q), f"Handbuch kennt '{q}' nicht"
assert manual.lookup("gibtsnicht") is None
assert manual.explain("rss").startswith("rss [url]")
assert "Message Base" in manual.catalog()
# Every command in the loop is documented (sample of the main commands)
for cmd in ("d", "s", "b", "f", "r", "l", "m", "a", "h", "sum", "ask", "go", "x", "chat", "ai", "fc", "c", "i", "t", "?", "q", "n", "rss", "dl"):
    assert manual.lookup(cmd), f"Befehl '{cmd}' fehlt im Handbuch"

# Token consumption
from bbs_browser.sysop import SysOp as _SysOp, estimate_cost, price_for
from bbs_browser.terminal import Terminal as _Terminal
from bbs_browser import db as _db
from bbs_browser import state as _state
assert price_for("claude-haiku-4-5") == (1.0, 5.0)
assert price_for("claude-opus-4-8") == (5.0, 25.0)
assert price_for("unbekannt") == (1.0, 5.0)          # fallback
assert estimate_cost("claude-haiku-4-5", 1_000_000, 1_000_000) == 6.0

class _FakeUsage:
    input_tokens = 1000; output_tokens = 500
    cache_creation_input_tokens = 0; cache_read_input_tokens = 200
class _FakeResp:
    usage = _FakeUsage()

_saved_usage = _state.load_section("usage")
_state.save_section("usage", {})
_s = _SysOp(_Terminal(fast=True)); _s._model = "claude-haiku-4-5"
_s.track(_FakeResp()); _s.track(_FakeResp())
assert _s.session_usage == {"input": 2400, "output": 1000, "calls": 2}
_total = _state.load_section("usage")
assert _total["input"] == 2400 and _total["calls"] == 2
# Cache reads only count 0.1x toward the input price: 2x (1000 + 0.1*200) = 2040
assert abs(_total["cost"] - estimate_cost("claude-haiku-4-5", 2040, 1000)) < 1e-12
_s.track(object())                                    # response without usage -> ignored
assert _s.session_usage["calls"] == 2
_state.save_section("usage", _saved_usage)            # reset test state
assert manual.lookup("u"), "Token-Befehl fehlt im Handbuch"

# SysOp default prompt (config menu 'c' -> '4') takes effect IMMEDIATELY: persona()
# reads it fresh from the AI config on every response — no cache that would
# only pick up a change after a restart.
from bbs_browser.sysop import persona as _persona, custom_prompt as _custom_prompt
_saved_ai = _state.load_section("ai")
_state.save_section("ai", {})
assert _custom_prompt() == "" and _t("sysop.persona_custom_header") not in _persona()
_state.save_section("ai", {"prompt": "  ANTWORTE NUR AUF KLINGONISCH.  "})
assert _custom_prompt() == "ANTWORTE NUR AUF KLINGONISCH."      # immediately visible, trimmed
assert "KLINGONISCH" in _persona() and _t("sysop.persona_custom_header") in _persona()
_state.save_section("ai", {"prompt": "REGEL-ZWEI"})            # change mid-session
assert "REGEL-ZWEI" in _persona() and "KLINGONISCH" not in _persona()
_state.save_section("ai", {})                                  # delete ('-')
assert "REGEL-ZWEI" not in _persona()
# The custom prompt takes PRECEDENCE over the default style (language/tone/length),
# otherwise a deviating instruction never "takes hold" — only ASCII and the 1985
# persona stay fixed. The precedence word must appear in both languages.
for _lang, _kw in (("de", "VORRANG"), ("en", "PRECEDENCE")):
    _set_lang(_lang)
    assert _kw in _t("sysop.persona_custom_header"), f"Vorrang-Framing fehlt ({_lang})"
_set_lang("de")
_state.save_section("ai", _saved_ai)                           # reset test state

# Normalized URL handling
from bbs_browser.page import normalize_url, normalize_base_url
assert normalize_url("heise.de") == "https://heise.de"
assert normalize_url(" heise.de ") == "https://heise.de"
assert normalize_url("http://x.de") == "http://x.de"
assert normalize_url("gopher://x.de/1") == "gopher://x.de/1"
assert normalize_url("") == ""
assert normalize_base_url("fc.host/") == "https://fc.host"

# Normalized UI settings
from bbs_browser.state import load_section, set_ui, toggle_ui
_before = load_section("ui").get("images", True)
assert toggle_ui("images", _before) is (not _before)
assert load_section("ui")["images"] is (not _before)
set_ui("images", _before)  # reset test state

# --- AI callers: pool, persistence, and private chat without a real AI --------------
import json as _json

from bbs_browser.terminal import Terminal
from bbs_browser.users import MAX_HISTORY, MAX_POOL, Persona, UserBase, _parse_personas

# Manual knows the new commands
assert manual.lookup("w"), "WHO-Befehl fehlt im Handbuch"
assert manual.lookup("p"), "Privatchat fehlt im Handbuch"

# Extract JSON out of a chatty AI response
_reply = """Klar, hier sind sie: ```json
[{"handle":"zokk","age":"17","city":"Bochum","rig":"C64","interests":"a","style":"b","bio":"c"},
 {"ohne":"handle"},
 {"handle":"ACID BURN"}]
``` viel Spass!"""
_parsed = _parse_personas(_reply)
assert [p.handle for p in _parsed] == ["ZOKK", "ACID BURN"], "Handles falsch geparst"
assert _parsed[0].age == 17, "Alter nicht als Zahl uebernommen"
assert _parse_personas("gar kein JSON") == []
assert _parse_personas(None) == []


class _FakeSysOp:
    """AI stand-in: returns canned replies, remembers the calls."""

    def __init__(self, replies, key=True):
        self.replies, self.key, self.calls = list(replies), key, []

    def has_key(self):
        return self.key

    def converse(self, system, messages, max_tokens=600):
        self.calls.append((system, list(messages)))
        return self.replies.pop(0) if self.replies else None


_saved_users = _state.load_section("users")
_state.save_section("users", {})
_term = Terminal(fast=True)

# Pool cap and history trim
_ub = UserBase(_term, _FakeSysOp([]))
_ub.save_pool([Persona(f"USER{i}") for i in range(MAX_POOL + 10)])
assert len(_ub.load_pool()) == MAX_POOL, "Pool nicht auf 20 gedeckelt"
_db.chat_clear(_ub.channel("ZOKK"))
for i in range(50):
    _ub.append_history("ZOKK", "user", str(i))
assert len(_ub.load_history("ZOKK")) == MAX_HISTORY, "Prompt-Fenster nicht getrimmt"
assert len(_db.chat_transcript(_ub.channel("ZOKK"), limit=200)) == 50, \
    "Voller Verlauf nicht in der DB"
_db.chat_clear(_ub.channel("ZOKK"))
assert _ub.load_history("ZOKK") == [], "Verlauf nicht geloescht"

# Broken state must not blow up
_state.save_section("users", {"pool": "kaputt"})
assert _ub.load_pool() == []

# Session selection: generated once, stays stable afterward
_state.save_section("users", {})
_gen = _json.dumps([
    {"handle": f"H{i}", "age": 20, "city": "X", "rig": "C64",
     "interests": "a", "style": "b", "bio": "c"}
    for i in range(8)
])
_sysop = _FakeSysOp([_gen, "hi, was geht?", "muss weg, ciao"])
_ub = UserBase(_term, _sysop)
_online = _ub.session_users()
assert _ub.session_users() is _online, "Session-Auswahl nicht stabil"
assert 3 <= len(_online) <= 8, "Unplausible Anzahl Anrufer"
assert len({e["node"] for e in _online}) == len(_online), "Node doppelt vergeben"
assert _ub.load_pool(), "Generierte Personas nicht gespeichert"

# Private chat: history is maintained and persisted per handle
_inputs = iter(["hallo", "und sonst?", ""])
_term.prompt = lambda label=None: next(_inputs)
_entry = _online[0]
_ub.chat_with(_entry)
_handle = _entry["persona"].handle
assert _ub.load_history(_handle) == [
    {"role": "user", "content": "hallo"},
    {"role": "assistant", "content": "hi, was geht?"},
    {"role": "user", "content": "und sonst?"},
    {"role": "assistant", "content": "muss weg, ciao"},
], "Chatverlauf nicht korrekt persistiert"
_system = _sysop.calls[-1][0]
assert _handle in _system and "1989" in _system, "Persona-Prompt ohne Rolle/Jahr"

# Knocked: the first line is pre-generated and is already in the chat
# the moment it's accepted — chat_with needs no further AI call for that
_entry_op = _online[1]
_handle_op = _entry_op["persona"].handle
_db.chat_clear(_ub.channel(_handle_op))
_opener_sysop = _FakeSysOp(["hoi, du auch noch wach?"])
_ub_op = UserBase(_term, _opener_sysop)
_opener = _ub_op._opener_line(_entry_op["persona"], _ub_op.load_history(_handle_op))
assert _opener == "hoi, du auch noch wach?"
_op_system, _op_messages = _opener_sysop.calls[0]
assert _handle_op in _op_system, "Opener ohne Persona-Prompt"
assert [m["role"] for m in _op_messages] == ["user"], "Opener-Aufruf falsch aufgebaut"
_term.prompt = lambda label=None: ""      # user hangs up immediately
_ub_op.chat_with(_entry_op, opener=_opener)
assert _ub_op.load_history(_handle_op) == [
    {"role": "assistant", "content": "hoi, du auch noch wach?"},
], "Anrufer hat den Chat nicht selbst eroeffnet"
assert len(_opener_sysop.calls) == 1, "chat_with darf die Zeile nicht nochmal generieren"

# Repeat knocker: the opener gets the prior history as context
_again_sysop = _FakeSysOp(["na, wieder da?"])
_ub_again = UserBase(_term, _again_sysop)
_hist = _ub_again.load_history(_handle_op)
assert _hist, "Vorgeschichte fehlt fuer den Wieder-Anklopfer"
assert _ub_again._opener_line(_entry_op["persona"], _hist) == "na, wieder da?"
_, _again_messages = _again_sysop.calls[0]
assert _again_messages[:-1] == _hist, "Verlauf nicht als Kontext mitgegeben"
assert _again_messages[-1]["role"] == "user", "Opener-Anweisung fehlt am Ende"

# maybe_knock: the knocker's message is generated BEFORE the
# chat request appears — it's there without delay once accepted
import random as _random
import time as _time
from bbs_browser.users import KNOCK_GAP
_db.chat_clear(_ub.channel(_handle_op))
_knock_sysop = _FakeSysOp(["moin, stoer ich?"])
_ub_knock = UserBase(_term, _knock_sysop)
_ub_knock._online = _online
_ub_knock._last_knock = _time.monotonic() - 10 * KNOCK_GAP
_rand_orig, _choice_orig = _random.random, _random.choice
_random.random = lambda: 0.0
_random.choice = lambda seq: _entry_op if seq is _online else _choice_orig(seq)
_knock_prompts = []
def _knock_prompt(label=None):
    _knock_prompts.append(len(_knock_sysop.calls))
    return "j" if len(_knock_prompts) == 1 else ""
_term.prompt = _knock_prompt
try:
    _ub_knock.maybe_knock()
finally:
    _random.random, _random.choice = _rand_orig, _choice_orig
assert _knock_prompts[0] == 1, "Eroeffnungszeile muss vor dem Chat-Request generiert sein"
assert _ub_knock.load_history(_handle_op) == [
    {"role": "assistant", "content": "moin, stoer ich?"},
], "Nachricht des Anklopfers fehlt im Chat"

# Without an opener the old flow remains: no self-typed first contact
_db.chat_clear(_ub.channel(_handle_op))
_plain_sysop = _FakeSysOp(["sollte nie erscheinen"])
_ub_plain = UserBase(_term, _plain_sysop)
_ub_plain.chat_with(_entry_op)
assert _ub_plain.load_history(_handle_op) == [], "Ohne opener darf niemand vorpreschen"
assert _plain_sysop.calls == [], "Ohne opener keinen KI-Aufruf erwartet"

# Without a key there are no callers — and no knocker
_ub_nokey = UserBase(_term, _FakeSysOp([], key=False))
assert not _ub_nokey.available()
assert _ub_nokey.maybe_knock() is None

_state.save_section("users", _saved_users)   # reset test state

# -- Page headers: all 50 templates exactly W characters wide ---------------
import unicodedata
from bbs_browser import headers as _headers

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _visual_width(text):
    """Visible columns — color codes don't count (the colored logo
    carries some), block graphics are narrow, CJK would be double width."""
    text = _ANSI_RE.sub("", text)
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)

assert len(_headers.TEMPLATES) == 50, "Es muessen 50 Header-Templates sein"
for _i, _tpl in enumerate(_headers.TEMPLATES, 1):
    for _dom in ("heise.de", "a.de", "x" * 90):          # short, minimal, overlong
        _f = _headers._fields(_dom)
        for _li, _line in enumerate(_tpl, 1):
            _w = _visual_width(_line.format(**_f))
            assert _w == _headers.W, f"Header T{_i:02d} Zeile {_li}: {_w} statt {_headers.W}"

# Assignment is stable and gets persisted
_saved_headers = _state.load_section("headers")
_headers.reset()
_first = _headers.template_for("beispiel.de")
assert _headers.template_for("beispiel.de") == _first, "Header-Zuordnung nicht stabil"
assert _state.load_section("headers")["beispiel.de"] == _first, "Zuordnung nicht gespeichert"
# The first 50 domains each get their own template
_headers.reset()
_idxs = [_headers.template_for(f"d{_n}.example") for _n in range(50)]
assert len(set(_idxs)) == 50, "Templates wiederholen sich zu frueh"
# Terminal too narrow: no header is better than a torn one
assert _headers.render("heise.de", 40) == [], "Header trotz zu schmalem Terminal"
assert _headers.render("", 100) == [], "Header ohne Domain"
_state.save_section("headers", _saved_headers)

# -- Image rendering ----------------------------------------------------------

from io import BytesIO as _BytesIO
from PIL import Image as _Image, ImageDraw as _ImageDraw


def _png(size, draw, mode="RGB", bg=(255, 255, 255)):
    img = _Image.new(mode, size, bg if mode == "RGB" else (0, 0, 0, 0))
    draw(_ImageDraw.Draw(img))
    buf = _BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


_foto = _png((400, 260), lambda d: (d.rectangle([0, 0, 400, 260], fill=(30, 30, 30)),
                                    d.ellipse([120, 50, 280, 210], fill=(255, 255, 255))))
_ascii = render_image(_foto, width=60, mode="ascii")
assert _ascii and _ascii["lines"], "Foto ergab keine ASCII-Art"
assert all(len(_l) == 60 for _l in _ascii["lines"]), "ASCII-Zeilen nicht auf Zielbreite"
# The ramp really needs to be exploited — otherwise auto-contrast doesn't kick in.
assert len(set("".join(_ascii["lines"]))) >= 4, "ASCII-Art nutzt zu wenige Stufen"

_blocks = render_image(_foto, width=60, mode="blocks")
assert _blocks and len(_blocks["luma"]) % 2 == 0, "Halbblock-Raster hat ungerade Zeilenzahl"
assert len(_blocks["luma"]) > len(_ascii["lines"]), "Halbbloecke ohne Aufloesungsgewinn"
_hb = halfblock_lines(_blocks["luma"], AMBER)
assert _hb and all(_l.count("▀") == 60 for _l in _hb), "Halbblock-Zeile nicht auf Zielbreite"

# Color depth depends on the terminal: 24-bit only with a COLORTERM signal. All
# other terminals silently round 38;2 down to their 256-color palette — fine
# gradients then turn into coarse stripes across the image. The fallback itself
# uses the phosphor tone's palette ramp and dithers the in-between tones.
_saved_colorterm = os.environ.get("COLORTERM")
os.environ["COLORTERM"] = "truecolor"
assert "\033[38;2;" in halfblock_lines(_blocks["luma"], AMBER)[0], \
    "Truecolor-Terminal bekommt keine 24-Bit-Farben"
os.environ["COLORTERM"] = ""
_hb256 = halfblock_lines(_blocks["luma"], AMBER)
assert all("[38;2" not in _l and "[48;2" not in _l for _l in _hb256), \
    "256-Farben-Terminal bekam 24-Bit-Sequenzen"
assert _hb256 and all(_l.count("▀") == 60 for _l in _hb256), \
    "256er-Zeilen nicht auf Zielbreite"
assert len({_m for _l in _hb256 for _m in re.findall(r"38;5;(\d+)m", _l)}) >= 3, \
    "256er-Bild nutzt zu wenige Palettenstufen"
if _saved_colorterm is None:
    del os.environ["COLORTERM"]
else:
    os.environ["COLORTERM"] = _saved_colorterm

# Tall images are capped to the page height (max_lines) so the label +
# image fit on one screen and the pager doesn't have to cut them apart.
_portrait = _png((300, 450), lambda d: (d.rectangle([0, 0, 300, 450], fill=(30, 30, 30)),
                                        d.ellipse([60, 80, 240, 370], fill=(255, 255, 255))))
assert len(render_image(_portrait, width=60, mode="blocks")["luma"]) // 2 > 20, \
    "Testbild zu niedrig fuer den Deckeltest"
_capped = render_image(_portrait, width=60, mode="blocks", max_lines=20)
assert len(_capped["luma"]) // 2 <= 20, "Bildhoehe nicht auf max_lines gedeckelt"
assert len(_capped["luma"][0]) < 60, "Deckel senkt die Breite nicht (Seitenverhaeltnis)"
assert len(render_image(_portrait, width=60, mode="ascii", max_lines=20)["lines"]) <= 20, \
    "ASCII-Bildhoehe nicht gedeckelt"
# Short image: the cap is above its height -> unchanged.
assert render_image(_foto, width=60, mode="ascii", max_lines=99)["lines"] == _ascii["lines"], \
    "Deckel verkleinert ein Bild, das ohnehin passt"

# Too small / too low-contrast: showing nothing is better than character mush
assert render_image(_png((48, 48), lambda d: None)) is None, "Icon wurde gerendert"
assert render_image(_png((400, 260), lambda d: None)) is None, "Einfarbige Flaeche gerendert"
assert render_image(b"kein bild") is None, "Kaputte Bytes ergaben ein Bild"

# Logo: dark brand mark on a transparent background -> the mark carries the ink, not the background
_logo = render_logo(_png((300, 90), lambda d: (d.ellipse([10, 15, 70, 75], fill=(20, 20, 20, 255)),
                                               d.rectangle([90, 30, 290, 60], fill=(20, 20, 20, 255))),
                         mode="RGBA"))
assert _logo and _logo.get("luma"), "Logo nicht im Blockmodus gerendert"
assert len(set(len(_r) for _r in _logo["luma"])) == 1, "Logo-Raster unterschiedlich breit"
assert len(_logo["luma"]) % 2 == 0, "Ungerade Bildzeilen — die letzte haette keinen Partner"
assert any(_p > 24 for _p in _logo["luma"][0]) or any(_p > 24 for _p in _logo["luma"][1]), \
    "Leerzeilen am Logo-Rand nicht entfernt"

_logo_ascii = render_logo(_png((300, 90), lambda d: (d.ellipse([10, 15, 70, 75], fill=(20, 20, 20, 255)),
                                                     d.rectangle([90, 30, 290, 60], fill=(20, 20, 20, 255))),
                               mode="RGBA"), mode="ascii")
_al = _logo_ascii["lines"]
assert _al[0].strip() and _al[-1].strip(), "Leerzeilen am Logo-Rand nicht entfernt"
assert len(set(len(_l) for _l in _al)) == 1, "Logo-Zeilen unterschiedlich breit (Zentrierung kippt)"
# Block mode has double the vertical resolution — legibility depends on it.
assert len(_logo["luma"]) == 2 * len(_al), "Blockmodus ohne doppelte Zeilenaufloesung"
assert render_logo(_png((300, 90), lambda d: None)) is None, "Leeres Logo durchgelassen"

# Logo banner: same width as the 50 static templates — in both modes,
# even though the block lines carry ANSI colors and are longer than they look.
for _art in (_logo, _logo_ascii):
    _lb = _headers.render("beispiel.de", 80, _art, "\033[38;5;214m")
    assert _lb and all(_visual_width(_l.strip()) == _headers.W for _l in _lb), \
        "Logo-Banner nicht W breit"

# -- Logo detection ---------------------------------------------------------

from bs4 import BeautifulSoup as _Soup

_logo_html = """<html><head>
<link rel="apple-touch-icon" sizes="57x57" href="/icons/small.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/big.png">
</head><body>
<header>
  <a href="/"><img src="/assets/marke.png" alt="Zur Startseite"></a>
  <a href="https://sportschau.de/"><img src="/assets/sportschau.png" alt="Sportschau Logo"></a>
</header>
<div><img src="/teaser/partner-logo-fremd.png" alt="Fremde Marke Logo"></div>
<div><img src="/assets/logo.svg" alt="Logo"></div>
</body></html>"""
_cands = find_logos(_Soup(_logo_html, "html.parser"), "https://test.de/artikel/1")
# The image inside the homepage link wins, the partner logo next to it drops out
assert _cands[0] == "https://test.de/assets/marke.png", f"falscher erster Kandidat: {_cands}"
assert not any("sportschau" in _c for _c in _cands), f"Fremdlogo aufgenommen: {_cands}"
assert not any(_c.endswith(".svg") for _c in _cands), "SVG aufgenommen — PIL kann das nicht"
# Of several icon sizes, the largest one first
assert "big.png" in _cands[1] and "small.png" in _cands[2], f"Icons falsch sortiert: {_cands}"

# -- Logo only on the first visit to a domain -------------------------------

from unittest import mock as _mock
from bbs_browser import browser as _browser


class _FakePage:
    def __init__(self, url):
        self.url, self.title, self.links, self.logo_urls = url, "t", [], ["x"]


_b = _browser.Browser.__new__(_browser.Browser)
_b.term = _mock.Mock(color="")
_b.header, _b.images, _b.color_auto = "logo", "blocks", False
_b._logo_domain = None
_seen = []
with _mock.patch.object(_browser.headers, "logo_art", lambda d, u, mode="blocks": ["ART"]), \
     _mock.patch.object(_browser.headers, "show", lambda term, dom, w, art: _seen.append(bool(art))), \
     _mock.patch.object(_browser, "paginate", lambda t, l: None), \
     _mock.patch.object(_browser, "layout_page", lambda *a: []):
    for _u in ("https://foo.de/a", "https://foo.de/b", "https://bar.de/x", "https://foo.de/c"):
        _b.page = _FakePage(_u)
        _b.show_page()
# First visit + every domain change shows the logo, subsequent pages of the same domain don't
assert _seen == [True, False, True, True], f"Logo-Reihenfolge falsch: {_seen}"

# -- Ctrl+C while dialing/searching only aborts the attempt, not the session ---
# Previously the KeyboardInterrupt propagated all the way up to the top-level
# loop and hung up the whole session ("NO CARRIER"). Now the loading path
# catches it and cleanly returns to the prompt (None), without presenting anything.
def _boom(*a, **k):
    raise KeyboardInterrupt

_bi = _browser.Browser.__new__(_browser.Browser)
_bi.term = _mock.Mock(color="")
_bi.images, _bi.img_width, _bi.firecrawl, _bi.sysop = "off", 60, {}, None
def _no_present(*a, **k):
    raise AssertionError("nach Abbruch darf nicht praesentiert werden")
_bi._present = _no_present
with _mock.patch.object(_browser, "fetch_page", _boom):
    assert _bi.dial("test.de") is None, "dial() gab bei Strg+C nicht None zurueck"
with _mock.patch.object(_browser, "ddg_search", _boom):
    assert _bi.search("frage") is None, "search() gab bei Strg+C nicht None zurueck"
assert _bi.term.error.called, "Abbruch wurde dem Anrufer nicht gemeldet"

# -- Strg+C im Lightbar-Menue: zurueck statt Verbindungsabbruch ----------
# Frueher flog der KeyboardInterrupt aus dem Menue bis in die Top-Level-Schleife
# und legte die ganze Session auf. Jetzt verhaelt sich das Menue wie der Prompt:
# einmal Strg+C geht eine Ebene zurueck (BACK) und fragt via on_interrupt nach.
import contextlib as _ctx

from bbs_browser import lightbar as _lb


@_ctx.contextmanager
def _fake_raw():
    yield


_term = _mock.Mock(color="", interrupts=0)
with _mock.patch.object(_lb.keys, "available", lambda: True), \
     _mock.patch.object(_lb.keys, "raw_mode", _fake_raw), \
     _mock.patch.object(_lb.keys, "read_key", _boom), \
     _mock.patch.object(_lb, "screen_width", lambda: 80):
    _choice = _lb.menu(_term, "T", [("a", "A", "")])
assert _choice == _lb.BACK, f"Strg+C im Menue gab {_choice!r} statt BACK"
assert _term.on_interrupt.called, "Menue hat Strg+C nicht wie am Prompt abgefragt"

# Strg+C im Spiel zaehlt als 'q' — es verlaesst das Spiel, nicht die Session.
from bbs_browser import keys as _keys

with _mock.patch.object(_keys, "wait_key", lambda t: True), \
     _mock.patch.object(_keys, "msvcrt", None), \
     _mock.patch.object(_keys.os, "read", lambda fd, n: b"\x03"):
    assert _keys.read_game_key(0) == "q", "Strg+C im Spiel wurde nicht zu 'q'"

# Strg+C am Passwort-Gate bricht nur die Eingabe ab (und verbraucht keinen der
# drei Versuche); erst das zweite Strg+C legt via on_interrupt auf.
from bbs_browser import nostalgia as _nost

_salt = "ab" * 16
_prof = {"pw_salt": _salt, "pw_hash": _nost._hash_password("geheim", _salt)}
_tries = iter([KeyboardInterrupt, KeyboardInterrupt, "falsch", "geheim"])


def _asks(term, label):
    nxt = next(_tries)
    if nxt is KeyboardInterrupt:
        raise KeyboardInterrupt
    return nxt


_gate_term = _mock.Mock(color="", interrupts=0)
with _mock.patch.object(_nost, "_ask_password", _asks):
    _nost._password_gate(_gate_term, _prof)
assert _gate_term.on_interrupt.call_count == 2, "Strg+C am Gate hat nicht nachgefragt"
assert next(_tries, "leer") == "leer", "Gate hat das richtige Passwort nicht mehr angenommen"

# -- MCP server: registration, auth methods, our own MCP client ----------
import json

from bbs_browser import mcp as _mcp

_mcp.save_servers([])
_mcp.upsert({"name": _mcp.unique_name("Demo Server!"), "url": "https://a/mcp",
             "auth": "bearer", "token": "geheim", "enabled": True})
assert [s["name"] for s in _mcp.load_servers()] == ["Demo_Server"], "Name nicht bereinigt"
assert _mcp.unique_name("Demo Server!") == "Demo_Server2", "Doppelter Name nicht entschaerft"

# An OAuth server without a token must not blow up the chat with a 401:
# it drops out of the tool list, the bearer server stays in.
_mcp.upsert({"name": "ohne_token", "url": "https://b/mcp", "auth": "oauth", "enabled": True})
assert _mcp.status(_mcp.find("ohne_token")) == "missing"

# Expired token without refresh: no access, but the entry stays.
_mcp.upsert({"name": "alt", "url": "https://c/mcp", "auth": "oauth",
             "token": "x", "expires_at": 1.0, "enabled": True})
assert _mcp.status(_mcp.find("alt")) == "expired"
assert _mcp.access_token(_mcp.find("alt")) == "x", "abgelaufener Token darf nicht verschwinden"


# Our own MCP client: initialize -> tools/list -> registry entries,
# tools/call delivers the text — all against a stubbed transport.
class _FakeResp:
    def __init__(self, body, session=None, ctype="application/json", code=200):
        self._body = body
        self.status_code = code
        self.headers = {"Content-Type": ctype}
        if session:
            self.headers["Mcp-Session-Id"] = session
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return json.loads(self.text)


_calls = []


def _fake_post(url, headers=None, data=None, timeout=None):
    msg = json.loads(data)
    _calls.append((msg.get("method"), headers.get("Mcp-Session-Id")))
    method = msg.get("method")
    if method == "initialize":
        return _FakeResp({"jsonrpc": "2.0", "id": msg["id"],
                          "result": {"protocolVersion": "2025-06-18"}}, session="s1")
    if method == "notifications/initialized":
        return _FakeResp("", code=202)
    if method == "tools/list":
        # As an SSE stream, so this path is also exercised.
        body = ("event: message\ndata: "
                + json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {
                    "tools": [{"name": "add task", "description": "Legt einen Task an.",
                               "inputSchema": {"type": "object",
                                               "properties": {"titel": {"type": "string"}}}}]}})
                + "\n\n")
        return _FakeResp(body, ctype="text/event-stream")
    if method == "tools/call":
        assert msg["params"] == {"name": "add task", "arguments": {"titel": "Test"}}
        return _FakeResp({"jsonrpc": "2.0", "id": msg["id"], "result": {
            "content": [{"type": "text", "text": "Task angelegt."}]}})
    raise AssertionError(f"unerwartete Methode {method}")


_real_post = _mcp.requests.post
_mcp.requests.post = _fake_post
try:
    _entries = _mcp.registry_tools()
    # Only the authenticated bearer server provides tools; the half-
    # authenticated OAuth servers aren't even contacted.
    assert [e["name"] for e in _entries] == ["Demo_Server__add_task"], _entries
    assert _entries[0]["parameters"]["properties"] == {"titel": {"type": "string"}}
    assert _entries[0]["func"](titel="Test") == "Task angelegt."
    # Session ID from initialize is sent along on subsequent calls.
    assert ("tools/list", "s1") in _calls and ("tools/call", "s1") in _calls
finally:
    _mcp.requests.post = _real_post
    _mcp._sessions.clear()
    _mcp._tool_cache.clear()

# Disabled servers never even reach the agent.
_deakt = _mcp.find("Demo_Server")
_deakt["enabled"] = False
_mcp.upsert(_deakt)
_mcp.requests.post = _fake_post
try:
    assert _mcp.registry_tools() == [], "Deaktivierter Server landet trotzdem beim Modell"
finally:
    _mcp.requests.post = _real_post
    _mcp._sessions.clear()
    _mcp._tool_cache.clear()

# Discovery tries the path variant first (RFC 9728), then the root path.
assert _mcp._well_known("https://h.de/mcp", "oauth-authorization-server") == [
    "https://h.de/.well-known/oauth-authorization-server/mcp",
    "https://h.de/.well-known/oauth-authorization-server",
]
_mcp.save_servers([])

# --- Door game 'The Ancient Wyrm' -----------------------------------------
from bbs_browser import dragon as _dragon

_hero = _dragon._fresh()
assert _dragon.max_hp(_hero) == 25 and _dragon.attack_power(_hero) > 0

# A fight with an invincible hero ends with 'win' and records loot.
class _AutoTerm:
    """Terminal stand-in: answers every combat prompt with 'attack'."""
    color = ""
    def type_out(self, *a, **k): pass
    def rule(self, *a, **k): pass
    def error(self, *a, **k): pass
    def box(self, *a, **k): pass
    def beep(self, *a, **k): pass
    def pause(self, *a, **k): pass
    def prompt(self, label=None): return "a"

_t_auto = _AutoTerm()
_hero["hp"] = 9999
_foe = _dragon.monster_for(1)
assert _dragon.fight(_t_auto, _hero, _foe) == "win"

# Whoever drops to 0 HP is out for today — gold is forfeited, experience stays.
_dead = _dragon._fresh()
_dead["hp"] = 1
_dead["gold"] = 500
_dead["exp"] = 42
assert _dragon.fight(_t_auto, _dead, {"name": "X", "hp": 10**6, "dmg": 50,
                                      "gold": 0, "exp": 0}) == "dead"
_dragon._died(_t_auto, _dead, {"name": "X"})
assert _dead["gold"] == 0 and _dead["exp"] == 42 and not _dead["alive"]

# The new game day wakes the fallen and refills the fight count.
_dragon.save_section(_dragon.SECTION, {**_dead, "day": "1989-01-01"})
_woken = _dragon.load_hero()
assert _woken["alive"] and _woken["fights"] == _dragon.FIGHTS_PER_DAY
assert _woken["hp"] == _dragon.max_hp(_woken)
_dragon.save_section(_dragon.SECTION, {})


# -- Cookie banner: gone, without ever consenting -------------------------------

_consent_html = """
<html><head><title>Zeitung</title></head><body>
<div id="onetrust-consent-sdk"><div id="onetrust-banner-sdk">
  <h2>Wir schaetzen Ihre Privatsphaere</h2>
  <p>Wir und unsere 1042 Partner speichern Cookies auf Ihrem Geraet.</p>
  <button>Alle akzeptieren</button></div></div>
<div class="cookie-banner-wrap"><p>Diese Website verwendet Cookies.</p></div>
<div id="CybelCookiebotDialog"><p>Kein echter Cookiebot — bleibt stehen.</p></div>
<div class="qc-cmp2-container"><p>Quantcast-Einwilligung</p></div>
<main><h1>Artikel</h1>
""" + "".join(f"<p>Absatz {i} des Artikels mit genug Text fuer eine vollwertige Seite.</p>"
               for i in range(8)) + """
</main></body></html>
"""

_consent_page = build_page(_consent_html, "https://zeitung.de/a", render_images=False)
_consent_text = " ".join(b.get("content", "") for b in _consent_page.blocks)
assert "Privatsphaere" not in _consent_text, "OneTrust-Banner ueberlebt"
assert "1042 Partner" not in _consent_text
assert "verwendet Cookies" not in _consent_text, "generischer Cookie-Banner ueberlebt"
assert "Quantcast" not in _consent_text
assert "Absatz 3" in _consent_text, "Artikel mit weggeraeumt"
# A full-screen modal carries almost the entire page text — the half-page
# brake of the general noise filter would let it stand, the CMP list won't.
_modal = build_page(
    '<html><body><div id="usercentrics-root"><p>' + "Einwilligung " * 200 +
    '</p></div><main><p>' + "Kurzer Artikel. " * 20 + '</p></main></body></html>',
    "https://zeitung.de/b", render_images=False)
assert "Einwilligung" not in " ".join(b.get("content", "") for b in _modal.blocks)

from bbs_browser import jsrender as _js
_yes = ("accept all", "allow all", "alle akzeptieren", "alle cookies erlauben",
        "accept cookies", "zustimmen", "einverstanden")
assert not any(y in p.lower() for p in _js._REJECT_PATTERNS for y in _yes), \
    "Zustimmung darf nicht geklickt werden"
assert any("without accepting" in p.lower() for p in _js._REJECT_PATTERNS)


# --- GET forms as input mask ('fm') ---------------------------------
from bbs_browser import forms as _forms

_form_html = f"""<html><title>T</title><body><main>
<form action="/suche" method="get" aria-label="Volltextsuche">
  <input type="hidden" name="site" value="alles">
  <label for="q">Suchbegriff</label><input type="text" id="q" name="q">
  <select name="sort"><option value="neu">Neueste</option>
    <option value="rel" selected>Relevanz</option></select>
  <input type="checkbox" name="archiv" value="1" checked>
  <input type="checkbox" name="bilder" value="1">
  <input type="submit" value="Los">
</form>
<form action="/login" method="get">
  <input type="text" name="user"><input type="password" name="pw">
</form>
<form action="/kommentar" method="post"><input type="text" name="c"></form>
<div class="cookie-banner"><form action="/consent" method="get">
  <input type="text" name="ok"></form></div>
{_pad}</main></body></html>"""
_fp = build_page(_form_html, "https://t.de/seite", render_images=False)

# Only the GET search mask remains: login (password), POST, and cookie banner get dropped.
assert len(_fp.forms) == 1
_mask = _fp.forms[0]
assert _mask["action"] == "https://t.de/suche" and _mask["label"] == "Volltextsuche"
# <label for> labels the field, the select list knows its preset value.
_vis = _forms.visible_fields(_mask)
assert [f["label"] for f in _vis] == ["Suchbegriff", "sort"]
assert _vis[1]["kind"] == "select" and _vis[1]["value"] == "rel"
# Hidden field and checked checkbox come along, the empty checkbox doesn't.
_hidden = {f["name"]: f["value"] for f in _mask["fields"] if f["kind"] == "hidden"}
assert _hidden == {"site": "alles", "archiv": "1"}
# Submitting is ultimately just an address.
assert _forms.submit_url(_mask, {"q": "amiga & modem", "sort": "neu"}) == \
    "https://t.de/suche?site=alles&q=amiga+%26+modem&sort=neu&archiv=1"
# Without input, the preset values apply.
assert _forms.submit_url(_mask, {}).endswith("?site=alles&q=&sort=rel&archiv=1")
# A form without an action submits back to its own page, the query gets replaced.
_self = build_page(f'<html><title>T</title><body><main><form method="get">'
                   f'<input type="text" name="q" value="rest"></form>{_pad}</main></body></html>',
                   "https://t.de/liste?alt=1", render_images=False)
assert _forms.submit_url(_self.forms[0], {}) == "https://t.de/liste?q=rest"
# The same search in the header and mobile version is ONE mask; without an
# aria-label, the first field labels the heading, never the developer's short code.
_dup = '<form action="/s" method="get" id="topnavi_search"><input type="text" name="q" placeholder="Suchen"></form>'
_dp = build_page(f"<html><title>T</title><body><main>{_dup}{_dup}{_pad}</main></body></html>",
                 "https://t.de", render_images=False)
assert len(_dp.forms) == 1 and _forms.form_title(_dp.forms[0], 1) == "Suchen"

# --- Style templates (`x`) -------------------------------------------
from bbs_browser import styletpl as _tpl

# DB round trip: store, list, delete.
assert _tpl.load("vorlage.de") is None
_tpl.save("vorlage.de", "modell-x", _tpl.skeleton("<html><body><div class='inhalt'>x</div></body></html>"),
          {"version": 1, "content": ".inhalt", "drop": [], "rules": [], "note": ""}, verified=2)
assert _tpl.exists("https://www.vorlage.de/seite")
assert _tpl.load("https://vorlage.de/seite")["content"] == ".inhalt"
assert any(r["domain"] == "vorlage.de" and r["verified"] == 2 for r in _tpl.domains())
_tpl.delete("vorlage.de")
assert not _tpl.exists("vorlage.de")

# Domain extraction: only http(s), "www." stripped, other schemes have none.
assert _tpl.domain_of("https://www.Heise.de/artikel") == "heise.de"
assert _tpl.domain_of("gopher://x.de/1") == ""

# sanitize(): unknown block kinds, broken selectors and cols on the wrong
# kind are thrown away; an entirely empty draft yields None.
_soup_probe = _BS("<html><body><h1 class='t'>T</h1></body></html>", "html.parser")
_clean = _tpl.sanitize({
    "content": "body",
    "drop": ["nav", "((("],
    "rules": [
        {"sel": "h1.t", "block": "banner"},
        {"sel": "h2", "block": "topicbar"},
        {"sel": "p.date", "block": "ticker"},
        {"sel": "p", "block": "quatsch"},
        {"sel": "(((", "block": "heading"},
        {"sel": "p", "block": "text"},
    ],
}, _soup_probe)
assert _clean["content"] == "body"
assert _clean["drop"] == ["nav"]
assert [(r["sel"], r["block"]) for r in _clean["rules"]] == [
    ("h1.t", "banner"), ("h2", "topicbar"), ("p.date", "ticker"), ("p", "text")]
assert _tpl.sanitize({"rules": [{"sel": "(((", "block": "text"}]}, _soup_probe) is None
assert _tpl.sanitize("kein json", _soup_probe) is None
# JSON out of a fenced answer is still found.
assert _tpl.sanitize('```json\n{"content": "body"}\n```', _soup_probe)["content"] == "body"

# Fingerprint: same structure ~ 1.0, foreign structure clearly below.
_skel_a = _tpl.skeleton("<html><body><div class='artikel'><p class='lead'>x</p></div></body></html>")
_skel_b = _tpl.skeleton("<html><body><div class='artikel'><p class='lead'>anderer Text</p></div></body></html>")
_skel_c = _tpl.skeleton("<html><body><section class='shop'><ul class='warenkorb'><li>x</li></ul></section></body></html>")
assert _tpl.similarity(_skel_a, _skel_b) == 1.0
assert _tpl.similarity(_skel_a, _skel_c) < _tpl.SIMILARITY_MIN

# Applying a template: the marked elements become BBS blocks, the content
# root wins over the heuristic and "drop" throws its selector away.
_tpl_html = ("<html><title>T</title><body>"
             "<div class='rand'>Werbung, die verschwinden soll.</div>"
             "<div class='artikel'>"
             "<h1 class='titel'>Schlagzeile</h1>"
             "<p class='lead'>Der Vorspann steht im Kasten und ist lang genug fuer eine Zeile.</p>"
             "<p>Der eigentliche Fliesstext des Artikels laeuft ueber mehrere Zeilen und "
             "traegt den groessten Teil des Textes dieser Seite mit sich herum.</p>"
             "</div></body></html>")
_tpl_data = {"version": 1, "content": ".artikel", "drop": [".rand"],
             "rules": [{"sel": "h1.titel", "block": "banner"},
                       {"sel": "p.lead", "block": "frame"}],
             "note": ""}
_styled = build_page(_tpl_html, "https://vorlage.de/a", render_images=False, template=_tpl_data)
_kinds = [b["type"] for b in _styled.blocks]
assert _kinds[0] == "banner" and _styled.blocks[0]["content"] == "Schlagzeile"
assert "frame" in _kinds
assert not any("Werbung" in b.get("content", "") for b in _styled.blocks)

# The fit check: a page whose structure drifted too far is left to the
# heuristic instead of being torn apart by the template.
_tpl_far = dict(_tpl_data, skeleton=_skel_c)
_unstyled = build_page(_tpl_html, "https://vorlage.de/a", render_images=False, template=_tpl_far)
assert not any(b["type"] == "banner" for b in _unstyled.blocks)

# check(): a template that shreds the page fails against the plain build.
_plain = build_page(_tpl_html, "https://vorlage.de/a", render_images=False)
assert _tpl.check(_styled, _plain)
_shredded = build_page(_tpl_html, "https://vorlage.de/a", render_images=False,
                       template={"version": 1, "content": "h1.titel", "drop": [], "rules": [], "note": ""})
assert not _tpl.check(_shredded, _plain)

# The Toolbox measures across ALL sample pages: preview only accepts a
# draft that survives every one of them.
_tpl_html2 = _tpl_html.replace("Schlagzeile", "Zweite Schlagzeile")
_samples = [_tpl.Sample("https://vorlage.de/a", _tpl_html, _plain),
            _tpl.Sample("https://vorlage.de/b", _tpl_html2,
                        build_page(_tpl_html2, "https://vorlage.de/b", render_images=False))]
_box = _tpl.Toolbox(_samples, lambda html, url, tpl: build_page(html, url, render_images=False, template=tpl))
_spec = _box.probe("h1.titel")
assert "GALLEY 2 (https://vorlage.de/b): 1 HITS" in _spec   # the selector holds on both
_report = _box.preview(_tpl_data)
assert "PROOF RUN: 2/2 GALLEYS PASSED" in _report and _box.best is not None and _box.verified == 2
_box.preview({"content": "h1.titel"})                 # shredding draft
assert _box.best["content"] == ".artikel"             # the good draft stays the best

# The content brake: a mark aimed at the whole container instead of the
# title is refused, so no body copy can vanish into a single block.
_greedy = {"version": 1, "content": "", "drop": [],
           "rules": [{"sel": ".artikel", "block": "banner"}], "note": ""}
_notes = []
_soup_greedy = _BS(_tpl_html, "html.parser")
_tpl.apply_to(_soup_greedy, _greedy, _notes)
assert _notes and "refused" in _notes[0] and _tpl.MARK_ATTR not in str(_soup_greedy)
_kept = build_page(_tpl_html, "https://vorlage.de/a", render_images=False, template=_greedy)
assert not any(b["type"] == "banner" for b in _kept.blocks)
assert _tpl.check(_kept, _plain)                      # not a single character lost
# ... and a "drop" that would take a quarter of the page with it is refused too.
_biggreed = {"version": 1, "content": "", "drop": [".artikel"], "rules": [], "note": ""}
_notes2 = []
_tpl.apply_to(_BS(_tpl_html, "html.parser"), _biggreed, _notes2)
assert _notes2 and "content, not noise" in _notes2[0]
assert _tpl.check(build_page(_tpl_html, "https://vorlage.de/a", render_images=False,
                             template=_biggreed), _plain)

# Pictures count as content: they are tallied even when images are switched
# off, a template that clears the page of them fails its proof, and a
# component mark is refused rather than swallowing a picture.
_pic_html = ("<html><title>T</title><body><div class='artikel'>"
             "<h1 class='titel'>Schlagzeile</h1>"
             "<figure class='bild'><img src='/gross.jpg' width='600' height='400' "
             "alt='Der neue Rechner im Labor'></figure>"
             "<p>Fliesstext des Artikels, der den groessten Teil der Seite ausmacht und "
             "ueber mehrere Zeilen laeuft, damit die Bilanz ueberhaupt eine Grundlage hat.</p>"
             "</div></body></html>")
_pic_plain = build_page(_pic_html, "https://bild.de/a", render_images=False)
assert _pic_plain.image_candidates == 1        # counted although images are off

# A drop that takes the picture with it loses the proof.
_blind = {"version": 1, "content": ".artikel", "drop": [".bild"], "rules": [], "note": ""}
_blind_page = build_page(_pic_html, "https://bild.de/a", render_images=False, template=_blind)
assert _blind_page.image_candidates == 0
assert _tpl.images_lost(_blind_page, _pic_plain) == 1
assert not _tpl.check(_blind_page, _pic_plain)
_dropnotes = []
_tpl.apply_to(_BS(_pic_html, "html.parser"), _blind, _dropnotes)
assert any("picture" in n for n in _dropnotes)

# A component aimed at the picture box is refused — the picture stays.
_swallow = {"version": 1, "content": ".artikel", "drop": [],
            "rules": [{"sel": "figure.bild", "block": "frame"}], "note": ""}
_kept_pic = build_page(_pic_html, "https://bild.de/a", render_images=False, template=_swallow)
assert _kept_pic.image_candidates == 1 and not any(b["type"] == "frame" for b in _kept_pic.blocks)
assert _tpl.check(_kept_pic, _pic_plain)

# The type case: every component the template may name is one the renderer
# can actually set, and each lands as its own recognisable block.
_case = {"version": 1, "content": "", "drop": [], "note": "",
         "rules": [{"sel": "h1.titel", "block": "banner"},
                   {"sel": "p.lead", "block": "plaque"}]}
_set = build_page(_tpl_html, "https://vorlage.de/a", render_images=False, template=_case)
assert [b["type"] for b in _set.blocks][:2] == ["banner", "plaque"]

from bbs_browser.page import Page as _CPage
_comp = _CPage("https://x.de", "T")
_comp.blocks = [{"type": "ticker", "content": "Zuerich, 14. Maerz 1985"},
                {"type": "topicbar", "content": "Aus der Redaktion"},
                {"type": "plaque", "content": "Kernaussage des Tages."},
                {"type": "notice", "content": "Achtung, Kickstart 1.2 noetig."}]
from bbs_browser.constants import screen_width as _sw
_clines = [_ANSI_RE.sub("", ln[1]) for ln in layout_page(_comp, AMBER)]
_joined = "\n".join(_clines)
assert ">>> ZUERICH, 14. MAERZ 1985 <<<" in _joined     # ticker
assert "──═[ AUS DER REDAKTION ]═" in _joined           # topic bar
assert "▒" in _joined and "┌" in _joined                # plaque with its shadow
assert any(ln.startswith("▌ ! Achtung") for ln in _clines)   # notice on its bar
# Every component line stays within the screen — nothing wraps into the next.
assert all(len(ln) <= _sw() for ln in _clines)

# A page built with a template says so — the browser reports it on dialing.
assert _styled.template_used and not _plain.template_used
_db.template_clear()

print("OK — alle Assertions bestanden")
