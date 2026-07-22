"""GET forms as BBS input masks.

Tier 1 of form support: `<form method="get">` — i.e. practically every
search field and filter bar on the web. Such a form is ultimately just a URL
with parameters; it is therefore submitted without a browser, without
JavaScript, and without a session, simply by dialing the assembled address.
POST forms and logins are left out — those need a session and only come with
later tiers.

Extraction runs in build_page, BEFORE the <form> tags are removed from the
document; the result is attached to the page as page.forms.
"""

from urllib.parse import urlencode, urljoin, urlparse, urlunparse

MAX_FORMS = 8          # more masks than this on one page helps no one
MAX_FIELDS = 12        # per mask — beyond this, nobody works their way through
MAX_OPTIONS = 20       # option lists get truncated beyond this point

# Input types we prompt for as a text field. Everything else (color, range,
# file, ...) can't be meaningfully operated from a BBS prompt.
TEXT_TYPES = {
    "", "text", "search", "email", "tel", "url", "number",
    "date", "time", "week", "month", "datetime-local",
}
# A form with one of these fields isn't a search mask: password means login
# (needs a session), file means upload (needs a body).
BLOCKING_TYPES = {"password", "file"}
IGNORED_TYPES = {"submit", "reset", "button", "image"}


def _text_of(tag, limit=40):
    return " ".join((tag.get_text(" ", strip=True) or "").split())[:limit]


def _label_for(form, field):
    """Label of a field — <label for=...>, enclosing <label>,
    aria-label, placeholder, and as a last resort the field name."""
    fid = field.get("id")
    if fid:
        for lab in form.find_all("label"):
            if lab.get("for") == fid:
                text = _text_of(lab)
                if text:
                    return text
    parent = field.find_parent("label")
    if parent is not None:
        text = _text_of(parent)
        if text:
            return text
    for attr in ("aria-label", "placeholder", "title", "name"):
        val = (field.get(attr) or "").strip()
        if val:
            return val[:40]
    return "?"


def _select_field(form, tag):
    options = []
    default = ""
    for opt in tag.find_all("option"):
        value = opt.get("value")
        if value is None:
            value = _text_of(opt, 60)
        label = _text_of(opt, 40) or value
        if not value and not label:
            continue
        options.append((value, label))
        if opt.has_attr("selected") and not default:
            default = value
    if not options:
        return None
    if not default:
        default = options[0][0]
    return {
        "name": tag.get("name", ""),
        "kind": "select",
        "label": _label_for(form, tag),
        "value": default,
        "options": options[:MAX_OPTIONS],
    }


def _fields(form):
    """The fields of a form in document order.
    Returns None if the form isn't a candidate for us."""
    out = []
    for tag in form.find_all(["input", "select", "textarea"]):
        name = (tag.get("name") or "").strip()
        if tag.name == "select":
            if not name:
                continue
            field = _select_field(form, tag)
            if field:
                out.append(field)
            continue
        if tag.name == "textarea":
            if name:
                out.append({"name": name, "kind": "text", "label": _label_for(form, tag),
                            "value": _text_of(tag, 200), "options": []})
            continue
        kind = (tag.get("type") or "text").strip().lower()
        if kind in BLOCKING_TYPES:
            return None           # login or upload — not tier 1
        if kind in IGNORED_TYPES or not name:
            continue
        value = (tag.get("value") or "").strip()
        if kind == "hidden":
            out.append({"name": name, "kind": "hidden", "label": name, "value": value, "options": []})
        elif kind in ("checkbox", "radio"):
            # Only carry over preset values — a browser never even sends
            # unchecked boxes in the first place.
            if tag.has_attr("checked"):
                out.append({"name": name, "kind": "hidden", "label": name,
                            "value": value or "on", "options": []})
        elif kind in TEXT_TYPES:
            out.append({"name": name, "kind": "text", "label": _label_for(form, tag),
                        "value": value, "options": []})
    return out


def _noise_ancestor(form):
    """Forms inside cookie banners, newsletter boxes & co. aren't an offer to
    the reader — the same noise filter used for body text."""
    from .page import NOISE_HINT_RE
    node = form
    for _ in range(6):
        if node is None or not getattr(node, "get", None):
            break
        blob = " ".join(node.get("class") or []) + " " + (node.get("id") or "")
        if NOISE_HINT_RE.search(blob):
            return True
        node = node.parent
    return False


def extract_forms(soup, base_url):
    """Collects all usable GET forms of a document.

    Duplicate masks are merged in the process: large pages like to put the
    same search into the HTML three times over (header, mobile version,
    sticky bar) — as an address, that's the same thing three times."""
    forms = []
    seen = set()
    for form in soup.find_all("form"):
        if len(forms) >= MAX_FORMS:
            break
        method = (form.get("method") or "get").strip().lower()
        if method != "get":
            continue
        if "multipart" in (form.get("enctype") or "").lower():
            continue
        action = urljoin(base_url, (form.get("action") or "").strip() or base_url)
        if urlparse(action).scheme not in ("http", "https"):
            continue
        if _noise_ancestor(form):
            continue
        fields = _fields(form)
        if not fields:
            continue
        if not any(f["kind"] != "hidden" for f in fields):
            continue          # only hidden fields — nothing to type
        fingerprint = (action, tuple(f["name"] for f in fields))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        # Only a genuine label is fit for use as a heading — 'name' and 'id'
        # are developer shorthand ("heisetopnavi_search") and help no one.
        label = (form.get("aria-label") or "").strip()
        forms.append({
            "action": action,
            "label": label[:40],
            "fields": fields[:MAX_FIELDS],
        })
    return forms


def visible_fields(form):
    return [f for f in form["fields"] if f["kind"] != "hidden"]


def form_title(form, index):
    """Heading of the mask: its own label, otherwise the first field."""
    if form["label"]:
        return form["label"]
    fields = visible_fields(form)
    if fields:
        return fields[0]["label"]
    return f"FORM {index}"


def submit_url(form, values):
    """The submitted address: the action's query is replaced, exactly as a
    real browser does with a GET form."""
    query = []
    for field in form["fields"]:
        value = values.get(field["name"], field["value"]) if field["kind"] != "hidden" else field["value"]
        if not field["name"]:
            continue
        query.append((field["name"], value))
    parts = urlparse(form["action"])
    return urlunparse(parts._replace(query=urlencode(query), fragment=""))
