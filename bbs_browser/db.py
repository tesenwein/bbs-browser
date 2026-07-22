"""SQLite persistence (~/.bbs_browser.db) — one file for everything.

Replaces the old JSON file (~/.bbs_browser.json for state and config)
and brings something the JSON storage couldn't: a persistent chat history.

Tables:
  sections   — state sections ("ui", "ai", "users", ...) as a JSON blob,
               so state.py keeps its familiar interface.
  chat_log   — every chat line with channel, role, and time.
  style_template — one learned style template per domain (`x`).

On first access, an existing JSON file is migrated into the DB once;
the original is left untouched (a safety net in case someone rolls
back to an older version).
"""

import json
import os
import sqlite3
import threading
import time

DB_FILE = os.path.expanduser("~/.bbs_browser.db")
LEGACY_STATE_FILE = os.path.expanduser("~/.bbs_browser.json")

MAX_CHAT_PER_CHANNEL = 400   # older lines per channel are discarded

_SCHEMA = """
-- Dropped with the AI page-design / welcome-art / per-page-rebuild removals;
-- kept so old DBs shed them.
DROP TABLE IF EXISTS style_profile;
DROP TABLE IF EXISTS design;
DROP TABLE IF EXISTS ai_page;
DROP TABLE IF EXISTS ai_domain;
CREATE TABLE IF NOT EXISTS sections (
    name TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    role    TEXT NOT NULL,
    content TEXT NOT NULL,
    display TEXT,
    ts      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS chat_log_channel ON chat_log (channel, id);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS style_template (
    domain   TEXT PRIMARY KEY,
    model    TEXT NOT NULL,
    skeleton TEXT NOT NULL,
    data     TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    ts       REAL NOT NULL
);
"""

_local = threading.local()


def _path():
    """The DB path. Redirectable via BBS_DB_FILE — the tests use this so
    that a test run doesn't touch the real mailbox."""
    return os.environ.get("BBS_DB_FILE") or DB_FILE


def connect():
    """Connection for this thread (sqlite3 connections can't be shared
    across threads). Sets up the schema and migration on first use."""
    path = _path()
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "path", None) == path:
        return conn
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    _local.conn = conn
    _local.path = path
    _migrate_legacy(conn)
    return conn


def close():
    """Close this thread's connection (tests, switching the DB's language)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    _local.conn = None
    _local.path = None


# -- Migration from the old JSON file ---------------------------------


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _migrate_legacy(conn):
    """One-time import. The marker in `meta` prevents later runs from
    overwriting the DB with stale JSON snapshots."""
    row = conn.execute("SELECT value FROM meta WHERE key = 'migrated'").fetchone()
    if row:
        return
    legacy_state = _read_json(LEGACY_STATE_FILE)
    # Bookmarks and history used to live at the top level; they move into
    # the "nav" section so everything is structured the same way.
    nav = {
        "bookmarks": legacy_state.pop("bookmarks", []),
        "history": legacy_state.pop("history", []),
    }
    if nav["bookmarks"] or nav["history"]:
        legacy_state["nav"] = nav
    # Private chats used to live as a dict in the "users" section — they
    # move into the chat history, where from now on they're kept in full
    # instead of just as a rolling window.
    users = legacy_state.get("users")
    legacy_chats = users.pop("chats", None) if isinstance(users, dict) else None
    for name, value in legacy_state.items():
        conn.execute(
            "INSERT OR REPLACE INTO sections (name, data) VALUES (?, ?)",
            (name, json.dumps(value)),
        )
    if isinstance(legacy_chats, dict):
        now = time.time()
        for handle, messages in legacy_chats.items():
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
                    continue
                conn.execute(
                    "INSERT INTO chat_log (channel, role, content, display, ts) VALUES (?, ?, ?, NULL, ?)",
                    (f"user:{handle}", msg["role"], str(msg.get("content", "")), now),
                )
    conn.execute("INSERT INTO meta (key, value) VALUES ('migrated', ?)", (str(time.time()),))
    conn.commit()


# -- State sections -------------------------------------------------------


def get_section(name):
    row = connect().execute("SELECT data FROM sections WHERE name = ?", (name,)).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["data"])
    except ValueError:
        return {}


def set_section(name, value):
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO sections (name, data) VALUES (?, ?)",
        (name, json.dumps(value)),
    )
    conn.commit()


# -- Chat history ------------------------------------------------------


def chat_append(channel, role, content, display=None):
    """Appends a line and trims the channel to MAX_CHAT_PER_CHANNEL."""
    conn = connect()
    conn.execute(
        "INSERT INTO chat_log (channel, role, content, display, ts) VALUES (?, ?, ?, ?, ?)",
        (channel, role, str(content), display, time.time()),
    )
    conn.execute(
        "DELETE FROM chat_log WHERE channel = ? AND id NOT IN "
        "(SELECT id FROM chat_log WHERE channel = ? ORDER BY id DESC LIMIT ?)",
        (channel, channel, MAX_CHAT_PER_CHANNEL),
    )
    conn.commit()


def chat_history(channel, limit=20):
    """The last `limit` lines as message dicts for the AI (oldest first)."""
    rows = connect().execute(
        "SELECT role, content FROM chat_log WHERE channel = ? ORDER BY id DESC LIMIT ?",
        (channel, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def chat_transcript(channel, limit=50):
    """Like chat_history, but for display: with timestamp and the short
    plain-text version instead of the prompt bloated with page context."""
    rows = connect().execute(
        "SELECT role, content, display, ts FROM chat_log WHERE channel = ? ORDER BY id DESC LIMIT ?",
        (channel, limit),
    ).fetchall()
    return [
        {"role": r["role"], "text": r["display"] or r["content"], "ts": r["ts"]}
        for r in reversed(rows)
    ]


def chat_channels():
    """All channels with line count and last activity, newest first."""
    rows = connect().execute(
        "SELECT channel, COUNT(*) AS n, MAX(ts) AS last FROM chat_log "
        "GROUP BY channel ORDER BY last DESC"
    ).fetchall()
    return [
        {"channel": r["channel"], "count": r["n"], "last": r["last"],
         "title": chat_title(r["channel"])}
        for r in rows
    ]


def _title_key(channel):
    return "chat_title:" + channel


def chat_title(channel):
    """The channel name assigned by the SysOp, or "" if none is set."""
    row = connect().execute(
        "SELECT value FROM meta WHERE key = ?", (_title_key(channel),)
    ).fetchone()
    return row["value"] if row else ""


def chat_set_title(channel, title):
    """Sets (or deletes, if the title is empty) a channel's name."""
    conn = connect()
    title = (title or "").strip()
    if title:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (_title_key(channel), title),
        )
    else:
        conn.execute("DELETE FROM meta WHERE key = ?", (_title_key(channel),))
    conn.commit()


def chat_clear(channel=None):
    conn = connect()
    if channel:
        conn.execute("DELETE FROM chat_log WHERE channel = ?", (channel,))
        conn.execute("DELETE FROM meta WHERE key = ?", (_title_key(channel),))
    else:
        conn.execute("DELETE FROM chat_log")
        conn.execute("DELETE FROM meta WHERE key LIKE 'chat_title:%'")
    conn.commit()


# -- Style templates (`x`) ------------------------------------------------


def template_get(domain):
    return connect().execute(
        "SELECT domain, model, skeleton, data, verified, ts "
        "FROM style_template WHERE domain = ?", (domain,)
    ).fetchone()


def template_put(domain, model, skeleton, data, verified=0):
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO style_template "
        "(domain, model, skeleton, data, verified, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (domain, model or "", skeleton or "", data, int(verified), time.time()),
    )
    conn.commit()


def template_delete(domain):
    conn = connect()
    conn.execute("DELETE FROM style_template WHERE domain = ?", (domain,))
    conn.commit()


def template_clear():
    conn = connect()
    conn.execute("DELETE FROM style_template")
    conn.commit()


def templates():
    """All learned templates, newest first."""
    rows = connect().execute(
        "SELECT domain, model, verified, ts FROM style_template ORDER BY ts DESC"
    ).fetchall()
    return [
        {"domain": r["domain"], "model": r["model"],
         "verified": r["verified"], "ts": r["ts"]}
        for r in rows
    ]
