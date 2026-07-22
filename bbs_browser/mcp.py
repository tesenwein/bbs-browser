"""Register custom MCP servers — with bearer token or OAuth.

Up to now the browser knew exactly one MCP server: the hardwired
Firecrawl service. This module turns that into a list that the caller
maintains themselves in the config menu ('c' > MCP). Each entry is a URL
plus a method for authenticating there:

    none    — open server, no token
    bearer  — a fixed token the caller enters once
    oauth   — the full dance: discovery, dynamic client registration, PKCE,
              browser login, callback on 127.0.0.1, background refresh

The browser fetches the active servers' tools itself: a deliberately small
MCP client (Streamable HTTP, JSON-RPC) queries tools/list and executes
tools/call. The results land as perfectly normal entries in the SysOp
agent's tool registry — this makes MCP servers work with any provider
(Anthropic, Vercel Gateway, OpenAI), not just Anthropic's own MCP
connector.

Everything lives in the "mcp" section of the database, tokens included, so
that a new call doesn't have to go through login again.
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
import webbrowser

import requests

from .state import load_section, save_section

AUTH_MODES = ("none", "bearer", "oauth")
HTTP_TIMEOUT = 15
CALLBACK_HOST = "127.0.0.1"
CALLBACK_TIMEOUT = 300          # how long login waits for the callback
TOKEN_SKEW = 60                 # seconds of safety margin before expiry
CLIENT_NAME = "BBS-Browser"
SCOPE_FALLBACK = ""


# -- Storage ----------------------------------------------------------------


def load_servers():
    """All registered servers (list of dicts, always with name/url/auth)."""
    servers = load_section("mcp").get("servers")
    if not isinstance(servers, list):
        return []
    return [s for s in servers if isinstance(s, dict) and s.get("url")]


def save_servers(servers):
    cfg = load_section("mcp")
    cfg["servers"] = servers
    save_section("mcp", cfg)


def find(name):
    for server in load_servers():
        if server.get("name") == name:
            return server
    return None


def upsert(server):
    """Creates a server or replaces the one with the same name."""
    servers = load_servers()
    for i, existing in enumerate(servers):
        if existing.get("name") == server.get("name"):
            servers[i] = server
            break
    else:
        servers.append(server)
    save_servers(servers)


def remove(name):
    save_servers([s for s in load_servers() if s.get("name") != name])


def unique_name(base):
    """A still-unused name — server names are the list's key."""
    base = _slug(base) or "mcp"
    taken = {s.get("name") for s in load_servers()}
    if base not in taken:
        return base
    i = 2
    while f"{base}{i}" in taken:
        i += 1
    return f"{base}{i}"


def _slug(text):
    """Connector names may only contain [a-zA-Z0-9_-]."""
    keep = [ch if (ch.isalnum() or ch in "_-") else "_" for ch in (text or "").strip()]
    return "".join(keep).strip("_")[:40]


def enabled_servers():
    return [s for s in load_servers() if s.get("enabled", True)]


# -- MCP client (Streamable HTTP) -------------------------------------------
#
# A deliberately small client: initialize, tools/list, tools/call. Sessions
# and tool lists live only in the process — the registry in the DB remains
# the single durable source of truth.

PROTOCOL_VERSION = "2025-06-18"
TOOL_CACHE_TTL = 300            # seconds before tools/list is queried again
MAX_TOOL_RESULT = 8000          # characters; the model doesn't see more

_sessions = {}                  # server name -> Mcp-Session-Id
_tool_cache = {}                # server name -> (expiry, tool list)


def _headers(server):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "MCP-Protocol-Version": PROTOCOL_VERSION}
    token = access_token(server)
    if token:
        headers["Authorization"] = "Bearer " + token
    session = _sessions.get(server["name"])
    if session:
        headers["Mcp-Session-Id"] = session
    return headers


def _parse_sse(text, rpc_id):
    """Fishes the JSON-RPC response with our id out of an SSE stream.

    Without an id match, the fallback only applies if the stream contained
    exactly ONE response (some servers omit the id) — with several it would
    be guesswork which one belongs to our request."""
    candidates = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            msg = json.loads(line[5:].strip())
        except ValueError:
            continue
        if isinstance(msg, dict) and ("result" in msg or "error" in msg):
            if msg.get("id") == rpc_id:
                return msg
            candidates.append(msg)
    return candidates[0] if len(candidates) == 1 else None


def _post(server, payload):
    """Sends a JSON-RPC message; returns (response_dict|None, error)."""
    resp = requests.post(server["url"], headers=_headers(server),
                         data=json.dumps(payload), timeout=HTTP_TIMEOUT)
    session = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
    if session:
        _sessions[server["name"]] = session
    if resp.status_code >= 400:
        return None, f"HTTP {resp.status_code}"
    if "id" not in payload:            # notification: no response expected
        return None, ""
    ctype = resp.headers.get("Content-Type", "")
    if "text/event-stream" in ctype:
        msg = _parse_sse(resp.text, payload["id"])
    else:
        try:
            msg = resp.json()
        except ValueError:
            msg = None
    if not isinstance(msg, dict):
        return None, "keine verwertbare Antwort"
    if msg.get("error"):
        return None, str(msg["error"].get("message") or msg["error"])
    return msg.get("result"), ""


def _rpc(server, method, params=None, _retry=True):
    """A call including session setup; on 404 it re-initializes once."""
    if server["name"] not in _sessions and method != "initialize":
        _initialize(server)
    payload = {"jsonrpc": "2.0", "id": 1, "method": method,
               "params": params or {}}
    try:
        result, err = _post(server, payload)
    except requests.RequestException as e:
        raise RuntimeError(str(e))
    if err == "HTTP 404" and _retry and method != "initialize":
        _sessions.pop(server["name"], None)     # session expired: start fresh
        _initialize(server)
        return _rpc(server, method, params, _retry=False)
    if err:
        raise RuntimeError(err)
    return result


def _initialize(server):
    _rpc(server, "initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": "1"},
    })
    try:
        _post(server, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    except requests.RequestException:
        pass                        # some servers don't like notifications


def list_tools(server):
    """All of a server's tools (tools/list, with pagination)."""
    tools, cursor, seen = [], None, set()
    while True:
        params = {"cursor": cursor} if cursor else {}
        result = _rpc(server, "tools/list", params) or {}
        tools.extend(result.get("tools") or [])
        cursor = result.get("nextCursor")
        # Repeated cursor = broken server; without this bailout it would loop forever.
        if not cursor or cursor in seen:
            return tools
        seen.add(cursor)


def call_tool(server, name, arguments):
    """Executes a tool and returns the result as text."""
    result = _rpc(server, "tools/call",
                  {"name": name, "arguments": arguments or {}}) or {}
    parts = []
    for block in result.get("content") or []:
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
        else:
            parts.append(json.dumps(block, ensure_ascii=False))
    text = "\n".join(p for p in parts if p) or json.dumps(
        result.get("structuredContent") or {}, ensure_ascii=False)
    if result.get("isError"):
        text = "Fehler vom MCP-Server: " + text
    return text[:MAX_TOOL_RESULT]


def registry_tools():
    """The tools of all active servers in the format of the SysOp tool
    registry (name/description/parameters/func). Unreachable or half
    authenticated servers drop out silently — a dead server must not
    take the chat down with it. The tool lists are cached briefly per
    process."""
    entries = []
    for server in enabled_servers():
        if server.get("auth", "none") != "none" and status(server) != "ok":
            continue
        cached = _tool_cache.get(server["name"])
        if cached and cached[0] > time.time():
            tools = cached[1]
        else:
            try:
                tools = list_tools(server)
            except (RuntimeError, requests.RequestException):
                continue
            _tool_cache[server["name"]] = (time.time() + TOOL_CACHE_TTL, tools)
        for tool in tools:
            name = f"{server['name']}__{_slug(tool.get('name', ''))}"[:64]
            schema = tool.get("inputSchema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema = {"type": "object", "properties": {}}
            entries.append({
                "name": name,
                "description": (tool.get("description") or "")[:1000]
                               or f"Werkzeug {tool.get('name')} des MCP-Servers {server['name']}.",
                "parameters": schema,
                "func": (lambda srv=server, tname=tool.get("name", ""), **kwargs:
                         call_tool(srv, tname, kwargs)),
            })
    return entries


def access_token(server):
    """A server's currently valid token, or "" if none is needed or none
    can be obtained. Silently refreshes expired OAuth tokens."""
    mode = server.get("auth", "none")
    if mode == "none":
        return ""
    if mode == "bearer":
        return server.get("token") or os.environ.get(server.get("token_env", ""), "")
    token = server.get("token") or ""
    expires = server.get("expires_at") or 0
    if token and (not expires or expires - TOKEN_SKEW > time.time()):
        return token
    refreshed = refresh(server)
    return refreshed or token


# -- OAuth: Discovery --------------------------------------------------------


def _get_json(url):
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT,
                            headers={"Accept": "application/json",
                                     "MCP-Protocol-Version": "2025-06-18"})
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _well_known(url, suffix):
    """RFC 8414/9728 place the metadata under /.well-known/<suffix> —
    once with the server's path appended, once without."""
    parts = urllib.parse.urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    candidates = [f"{root}/.well-known/{suffix}"]
    if path:
        candidates.insert(0, f"{root}/.well-known/{suffix}{path}")
    return candidates


def discover(url):
    """Find authorization metadata for an MCP server.

    Path 1: the server itself names its authorization server via
    protected-resource metadata. Path 2 (fallback): the server IS its own
    authorization server. Returns the metadata dict or None."""
    issuers = []
    for candidate in _well_known(url, "oauth-protected-resource"):
        meta = _get_json(candidate)
        if meta and meta.get("authorization_servers"):
            issuers = [i for i in meta["authorization_servers"] if isinstance(i, str)]
            break
    for issuer in issuers + [url]:
        for suffix in ("oauth-authorization-server", "openid-configuration"):
            for candidate in _well_known(issuer, suffix):
                meta = _get_json(candidate)
                if meta and meta.get("authorization_endpoint") and meta.get("token_endpoint"):
                    return meta
    return None


def register_client(meta, redirect_uri):
    """Dynamic Client Registration (RFC 7591). Returns (client_id, secret)
    or (None, None) if the server doesn't offer open registration."""
    endpoint = meta.get("registration_endpoint")
    if not endpoint:
        return None, None
    payload = {
        "client_name": CLIENT_NAME,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=HTTP_TIMEOUT)
    except requests.RequestException:
        return None, None
    if resp.status_code not in (200, 201):
        return None, None
    try:
        data = resp.json()
    except ValueError:
        return None, None
    return data.get("client_id"), data.get("client_secret")


# -- OAuth: login with PKCE --------------------------------------------------


def _pkce():
    verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Accepts exactly one callback and stores it on the server."""

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        self.server.result = urllib.parse.parse_qs(query)
        body = (b"<html><body style='font-family:monospace;background:#111;color:#0f0'>"
                b"<h2>BBS-BROWSER</h2><p>Anmeldung abgeschlossen. "
                b"Dieses Fenster kann geschlossen werden.</p></body></html>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # the terminal belongs to the BBS, not the HTTP server


def _free_port():
    with socket.socket() as sock:
        sock.bind((CALLBACK_HOST, 0))
        return sock.getsockname()[1]


def login(server, notify=None):
    """Runs the OAuth flow for a server and stores the tokens.

    `notify(key, **kwargs)` reports progress (the menu layer hooks its
    translated output in there). Returns (True, "") or (False, reason).
    """
    say = notify or (lambda *a, **k: None)
    meta = server.get("oauth") or {}
    endpoints = meta.get("meta")
    if not endpoints:
        say("discover")
        endpoints = discover(server["url"])
        if not endpoints:
            return False, "no-metadata"
        meta["meta"] = endpoints

    port = _free_port()
    redirect_uri = f"http://{CALLBACK_HOST}:{port}/callback"
    client_id = meta.get("client_id")
    if not client_id:
        say("register")
        client_id, client_secret = register_client(endpoints, redirect_uri)
        if not client_id:
            return False, "no-client"
        meta["client_id"] = client_id
        if client_secret:
            meta["client_secret"] = client_secret

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)
    scope = meta.get("scope") or " ".join(endpoints.get("scopes_supported") or []) or SCOPE_FALLBACK
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": server["url"],
    }
    if scope:
        params["scope"] = scope
    auth_url = endpoints["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)

    httpd = http.server.HTTPServer((CALLBACK_HOST, port), _CallbackHandler)
    httpd.result = None
    httpd.timeout = 1
    thread = threading.Thread(target=_serve_once, args=(httpd,), daemon=True)
    thread.start()
    say("open_browser", url=auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    thread.join(CALLBACK_TIMEOUT)
    result = httpd.result
    httpd.server_close()
    if not result:
        return False, "timeout"
    if result.get("error"):
        return False, result["error"][0]
    if result.get("state", [None])[0] != state:
        return False, "state-mismatch"
    code = result.get("code", [None])[0]
    if not code:
        return False, "no-code"

    say("exchange")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
        "resource": server["url"],
    }
    if meta.get("client_secret"):
        data["client_secret"] = meta["client_secret"]
    token, err = _token_request(endpoints["token_endpoint"], data)
    if not token:
        return False, err
    meta["scope"] = scope
    server["oauth"] = meta
    _store_token(server, token)
    return True, ""


def _serve_once(httpd):
    """Serves requests until the callback arrives (or time runs out)."""
    deadline = time.time() + CALLBACK_TIMEOUT
    while httpd.result is None and time.time() < deadline:
        httpd.handle_request()


def _token_request(endpoint, data):
    """POST to the token endpoint. Returns (token_dict, "") or (None, reason)."""
    try:
        resp = requests.post(endpoint, data=data, timeout=HTTP_TIMEOUT,
                             headers={"Accept": "application/json"})
    except requests.RequestException as e:
        return None, str(e)
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    if resp.status_code != 200 or not payload.get("access_token"):
        return None, payload.get("error_description") or payload.get("error") or f"HTTP {resp.status_code}"
    return payload, ""


def _store_token(server, token):
    """Attaches tokens to the server entry and saves it."""
    server["auth"] = "oauth"
    server["token"] = token["access_token"]
    if token.get("refresh_token"):
        server["refresh_token"] = token["refresh_token"]
    expires_in = token.get("expires_in")
    server["expires_at"] = time.time() + float(expires_in) if expires_in else 0
    upsert(server)


def refresh(server):
    """Refreshes an expired OAuth token. Returns the new token or ""."""
    meta = server.get("oauth") or {}
    endpoints = meta.get("meta") or {}
    if not server.get("refresh_token") or not endpoints.get("token_endpoint"):
        return ""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": server["refresh_token"],
        "client_id": meta.get("client_id", ""),
        "resource": server["url"],
    }
    if meta.get("client_secret"):
        data["client_secret"] = meta["client_secret"]
    token, _ = _token_request(endpoints["token_endpoint"], data)
    if not token:
        return ""
    _store_token(server, token)
    return token["access_token"]


def logout(server):
    """Forgets a server's tokens; the registration remains in place."""
    for key in ("token", "refresh_token", "expires_at"):
        server.pop(key, None)
    upsert(server)


def status(server):
    """Short status for the menu display: 'ok', 'expired', 'missing', 'open'."""
    mode = server.get("auth", "none")
    if mode == "none":
        return "open"
    if mode == "bearer":
        return "ok" if access_token(server) else "missing"
    if not server.get("token"):
        return "missing"
    expires = server.get("expires_at") or 0
    if expires and expires - TOKEN_SKEW <= time.time() and not server.get("refresh_token"):
        return "expired"
    return "ok"


def probe(server):
    """Quick reachability test: sends an MCP initialize request.

    Returns (True, "") for a usable response, otherwise (False, reason).
    A 401 is the interesting outcome here — it means authentication is missing."""
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "MCP-Protocol-Version": "2025-06-18"}
    token = access_token(server)
    if token:
        headers["Authorization"] = "Bearer " + token
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": CLIENT_NAME, "version": "1"},
        },
    }
    try:
        resp = requests.post(server["url"], headers=headers, data=json.dumps(body),
                             timeout=HTTP_TIMEOUT, stream=True)
    except requests.RequestException as e:
        return False, str(e)
    code = resp.status_code
    resp.close()
    if code == 401:
        return False, "401"
    if code >= 400:
        return False, f"HTTP {code}"
    return True, ""
