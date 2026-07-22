"""Retro-Protokolle: Gopher (Port 70) und Gemini (Port 1965).

Beide passen perfekt ins BBS: reiner Text, Menues, keine Cookies, kein JS.
Anwahl ganz normal mit 'd gopher://gopher.floodgap.com' oder
'd gemini://geminiprotocol.net'.
"""

import socket
import ssl
from urllib.parse import unquote, urlparse

from .i18n import t

MAX_REDIRECTS = 5
TIMEOUT = 15


def _get_gopher_types():
    return {
        "0": t("retronet.type_txt"),
        "1": t("retronet.type_dir"),
        "7": t("retronet.type_search"),
        "h": t("retronet.type_www"),
        "g": t("retronet.type_gif"),
        "I": t("retronet.type_image"),
        "9": t("retronet.type_bin"),
        "5": t("retronet.type_bin"),
    }


def _page(url, title):
    from .page import Page
    return Page(url, title)


def _recv_all(sock, limit=2_000_000):
    data = b""
    while len(data) < limit:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


# -- Gopher --------------------------------------------------------------

def parse_gopher_menu(text, url):
    """Baut aus einem Gopher-Menue eine Seite mit nummerierten Links."""
    page = _page(url, url)
    gopher_types = _get_gopher_types()
    for raw in text.splitlines():
        if raw == "." or not raw:
            continue
        itype, rest = raw[:1], raw[1:]
        cols = rest.split("\t")
        label = cols[0].strip()
        if itype == "i":
            if label:
                page.blocks.append({"type": "text", "content": label})
            continue
        if len(cols) < 3 or not label:
            continue
        selector, host = cols[1], cols[2]
        port = cols[3].strip() if len(cols) > 3 and cols[3].strip() else "70"
        if itype == "h" and selector.startswith("URL:"):
            target = selector[4:]
        else:
            portpart = "" if port == "70" else f":{port}"
            target = f"gopher://{host}{portpart}/{itype}{selector}"
        num = page.add_link(target, label)
        tag = gopher_types.get(itype, itype)
        marker = f"[{num}]" if num else ""
        page.blocks.append({"type": "text", "content": f"({tag}) {label}{marker}"})
    return page


def fetch_gopher(url):
    p = urlparse(url)
    host, port = p.hostname, p.port or 70
    path = unquote(p.path or "")
    gtype, selector = "1", ""
    if len(path) >= 2:
        gtype, selector = path[1], path[2:]
    if p.query:  # Typ-7-Suche: Selector <TAB> Suchbegriff
        selector += "\t" + unquote(p.query)
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as s:
            s.sendall((selector + "\r\n").encode("utf-8", "replace"))
            data = _recv_all(s)
    except Exception as e:
        return None, t("retronet.gopher_error", error=str(e))
    text = data.decode("utf-8", "replace")
    if gtype == "0":
        page = _page(url, f"gopher://{host}{p.path}")
        page.blocks.append({"type": "pre", "content": text.rstrip().removesuffix("\n.")})
        return page, None
    page = parse_gopher_menu(text, url)
    page.title = f"gopher://{host}{p.path or '/'}"
    return page, None


# -- Gemini --------------------------------------------------------------

def _gemini_join(base, ref):
    """urljoin kennt das gemini-Schema nicht — ueber http tricksen."""
    from urllib.parse import urljoin
    if "://" in ref:
        return ref
    return urljoin(base.replace("gemini://", "http://", 1), ref).replace("http://", "gemini://", 1)


def parse_gemtext(text, url):
    """Baut aus text/gemini eine Seite mit nummerierten Links."""
    page = _page(url, url)
    pre = False
    pre_lines = []
    for raw in text.splitlines():
        if raw.startswith("```"):
            if pre and pre_lines:
                page.blocks.append({"type": "pre", "content": "\n".join(pre_lines)})
                pre_lines = []
            pre = not pre
            continue
        if pre:
            pre_lines.append(raw)
            continue
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("=>"):
            parts = line[2:].strip().split(None, 1)
            if not parts:
                continue
            target = _gemini_join(url, parts[0])
            label = parts[1].strip() if len(parts) > 1 else parts[0]
            num = page.add_link(target, label)
            marker = f"[{num}]" if num else ""
            page.blocks.append({"type": "text", "content": f"{label}{marker}"})
        elif line.startswith("#"):
            page.blocks.append({"type": "heading", "content": line.lstrip("# ").strip()})
            if page.title == url:
                page.title = line.lstrip("# ").strip()
        elif line.startswith(">"):
            page.blocks.append({"type": "text", "content": "» " + line.lstrip("> ")})
        elif line.startswith("*"):
            page.blocks.append({"type": "text", "content": "· " + line.lstrip("* ")})
        else:
            page.blocks.append({"type": "text", "content": line})
    if pre_lines:
        page.blocks.append({"type": "pre", "content": "\n".join(pre_lines)})
    return page


def fetch_gemini(url, _hops=0):
    if _hops > MAX_REDIRECTS:
        return None, t("retronet.gemini_too_many_redirects")
    p = urlparse(url)
    host, port = p.hostname, p.port or 1965
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Gemini nutzt TOFU statt CA-Zertifikate
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as s:
                s.sendall((url + "\r\n").encode())
                data = _recv_all(s)
    except Exception as e:
        return None, t("retronet.gemini_error", error=str(e))
    header, _, body = data.partition(b"\r\n")
    status = header.decode("utf-8", "replace").strip()
    code, _, meta = status.partition(" ")
    if code.startswith("3"):
        return fetch_gemini(_gemini_join(url, meta.strip()), _hops + 1)
    if code.startswith("1"):
        return None, t("retronet.gemini_input_required", meta=meta.strip())
    if not code.startswith("2"):
        return None, t("retronet.gemini_status_error", status=status)
    text = body.decode("utf-8", "replace")
    if not meta.strip().startswith("text/gemini") and not meta.strip().startswith("text/"):
        return None, t("retronet.gemini_unsupported_type", type=meta.strip())
    if meta.strip().startswith("text/") and "gemini" not in meta:
        page = _page(url, url)
        page.blocks.append({"type": "pre", "content": text.rstrip()})
        return page, None
    return parse_gemtext(text, url), None
