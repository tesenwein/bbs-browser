"""AI callers: the other users currently hanging around on the mailbox.

Each caller is an AI-generated persona, firmly anchored in the 1980s.
The pool grows across sessions up to MAX_POOL and lives in the "users"
section of the database — not in the cache, which discards after 7 days.
The private chats themselves live in the persistent chat history (channel
"user:<handle>").

Commands: 'w' lists who's dialed in, 'p <nr>' opens a private chat.
Occasionally someone also knocks on their own (maybe_knock).
"""

import json
import random
import time

from . import db
from .browser import MAX_NODES
from .i18n import t
from .state import load_section, save_section

MAX_POOL = 20          # at most this many personas get built up
MAX_HISTORY = 20       # chat entries per handle — keeps the prompt small
ONLINE_MIN, ONLINE_MAX = 3, 8
MAX_NODE = 12          # total nodes; 1..MAX_NODES are your own lines
BAUD_RATES = (300, 1200, 2400, 9600, 14400, 19200)
KNOCK_CHANCE = 0.05    # per command prompt
KNOCK_GAP = 240        # minimum seconds between two knock requests

PERSONA_FIELDS = ("handle", "age", "city", "rig", "interests", "style", "bio")

ACTION_KEYS = (
    "reading", "downloading", "uploading", "doors", "mail",
    "idle", "chatting", "filelist", "bulletins", "logon",
)


class Persona:
    """A made-up caller. Deliberately lenient: missing fields become ""."""

    __slots__ = PERSONA_FIELDS

    def __init__(self, handle, age=0, city="", rig="", interests="", style="", bio=""):
        self.handle = handle
        self.age = age
        self.city = city
        self.rig = rig
        self.interests = interests
        self.style = style
        self.bio = bio

    @classmethod
    def from_dict(cls, data):
        """Builds a persona from raw JSON. Returns None if there is no handle —
        everything else may be missing."""
        if not isinstance(data, dict):
            return None
        handle = str(data.get("handle", "")).strip().upper()[:16]
        if not handle:
            return None
        try:
            age = int(data.get("age", 0) or 0)
        except (TypeError, ValueError):
            age = 0
        return cls(
            handle=handle,
            age=age,
            city=str(data.get("city", "") or "")[:60],
            rig=str(data.get("rig", "") or "")[:80],
            interests=str(data.get("interests", "") or "")[:120],
            style=str(data.get("style", "") or "")[:160],
            bio=str(data.get("bio", "") or "")[:600],
        )

    def to_dict(self):
        return {field: getattr(self, field) for field in PERSONA_FIELDS}


def _parse_personas(text):
    """Extracts a JSON array from the AI response. Models like to wrap it in
    a code block or a preamble — so trim down to the brackets."""
    if not text:
        return []
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        raw = json.loads(text[start:end + 1])
    except ValueError:
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        persona = Persona.from_dict(item)
        if persona:
            out.append(persona)
    return out


class UserBase:
    """Pool, session selection, and chats of the AI callers."""

    def __init__(self, term, sysop):
        self.term = term
        self.sysop = sysop
        self._online = None            # session selection, stable in RAM
        self._last_knock = time.monotonic()

    # -- Persistence -------------------------------------------------------

    @staticmethod
    def _section():
        data = load_section("users")
        return data if isinstance(data, dict) else {}

    def load_pool(self):
        raw = self._section().get("pool")
        if not isinstance(raw, list):
            return []
        pool, seen = [], set()
        for item in raw:
            persona = Persona.from_dict(item)
            if persona and persona.handle not in seen:
                seen.add(persona.handle)
                pool.append(persona)
        return pool[:MAX_POOL]

    def save_pool(self, pool):
        data = self._section()
        data["pool"] = [p.to_dict() for p in pool[:MAX_POOL]]
        save_section("users", data)

    @staticmethod
    def channel(handle):
        """This caller's channel name in the persistent chat history."""
        return f"user:{handle}"

    def load_history(self, handle):
        """Only the prompt window — the DB holds the full history."""
        return db.chat_history(self.channel(handle), limit=MAX_HISTORY)

    def append_history(self, handle, role, content):
        db.chat_append(self.channel(handle), role, content)

    # -- AI generation -------------------------------------------------

    def _generate(self, count, avoid):
        """Has the AI invent `count` new personas. Empty list on error."""
        if count <= 0:
            return []
        self.term.type_out(t("users.dialing_nodes"), delay=0.003)
        prompt = t(
            "users.generator_prompt",
            count=count,
            avoid=", ".join(avoid) if avoid else t("users.generator_none"),
        )
        text = self.sysop.converse(
            t("users.generator_system"),
            [{"role": "user", "content": prompt}],
            max_tokens=400 * count,
        )
        taken = {h.upper() for h in avoid}
        fresh = []
        for persona in _parse_personas(text):
            if persona.handle not in taken:
                taken.add(persona.handle)
                fresh.append(persona)
        return fresh[:count]

    # -- Session selection -------------------------------------------------

    def available(self):
        """Callers only if a key is configured."""
        return bool(self.sysop and self.sysop.has_key())

    def session_users(self, generate=True):
        """The callers dialed in for this session — drawn once, then
        stable, so that 'w' and 'p <nr>' stay consistent."""
        if self._online is not None:
            return self._online
        pool = self.load_pool()
        if generate:
            want = random.randint(ONLINE_MIN, ONLINE_MAX)
            missing = min(want, MAX_POOL) - len(pool)
            if missing > 0:
                fresh = self._generate(missing, [p.handle for p in pool])
                if fresh:
                    pool = (pool + fresh)[:MAX_POOL]
                    self.save_pool(pool)
        if not pool:
            return None
        count = min(len(pool), random.randint(ONLINE_MIN, ONLINE_MAX))
        # Callers sit on the nodes behind your own lines — this way none of
        # them collide with the node number the header shows for you.
        nodes = random.sample(range(MAX_NODES + 1, MAX_NODE + 1), count)
        self._online = [
            {
                "persona": persona,
                "node": node,
                "baud": random.choice(BAUD_RATES),
                "idle": random.randint(0, 47),          # minutes
                "action": t("users.action_" + random.choice(ACTION_KEYS)),
            }
            for persona, node in zip(random.sample(pool, count), nodes)
        ]
        return self._online

    def online_count(self):
        """How many AI callers are currently dialed in — used by the
        welcome box, so no AI call is made: only drawn from the stored
        pool. 0 without a key or while the pool is still empty."""
        if not self.available():
            return 0
        return len(self.session_users(generate=False) or ())

    # -- 'w': WHO list -------------------------------------------------

    def who(self):
        term = self.term
        if not self.available():
            term.error(t("users.error_no_key"))
            return
        entries = self.session_users()
        if not entries:
            term.error(t("users.error_no_users"))
            return
        term.rule(t("users.who_title"))
        term.type_out(t("users.who_header"), delay=0.001)
        for i, entry in enumerate(entries, 1):
            idle = f"{entry['idle'] // 60}:{entry['idle'] % 60:02d}"
            term.type_out(
                f" {i:>2}   {entry['node']:>3}  {entry['persona'].handle[:15]:<15}"
                f"{entry['baud']:>6}  {idle:>5}  {entry['action']}",
                delay=0.001,
            )
        term.type_out(t("users.who_footer", count=len(entries)), delay=0.002)
        term.rule()

    # -- 'p <nr>': private chat -------------------------------------------------

    def private_chat(self, arg):
        term = self.term
        if not self.available():
            term.error(t("users.error_no_key"))
            return
        arg = (arg or "").strip()
        if not arg.isdigit():
            term.error(t("users.error_p_usage"))
            return
        entries = self.session_users()
        if not entries:
            term.error(t("users.error_no_users"))
            return
        num = int(arg)
        if not 1 <= num <= len(entries):
            term.error(t("users.error_bad_number", num=num))
            return
        self.chat_with(entries[num - 1])

    def resume_chat(self, handle):
        """Entry point from 'log <nr> chat': resume the private chat with
        this handle. Whoever is currently dialed in keeps their node; all
        others get a freshly rolled one for the session."""
        term = self.term
        if not self.available():
            term.error(t("users.error_no_key"))
            return
        handle = (handle or "").strip().upper()
        for entry in self.session_users(generate=False) or ():
            if entry["persona"].handle == handle:
                self.chat_with(entry)
                return
        for persona in self.load_pool():
            if persona.handle == handle:
                self.chat_with({
                    "persona": persona,
                    "node": random.randint(MAX_NODES + 1, MAX_NODE),
                    "baud": random.choice(BAUD_RATES),
                    "idle": 0,
                    "action": t("users.action_chatting"),
                })
                return
        term.error(t("users.error_unknown_handle", handle=handle))

    def _persona_system(self, persona):
        """As a function, not a module constant — otherwise the text would
        freeze in whatever language was active at import time."""
        return t("users.persona_system", **persona.to_dict())

    def chat_with(self, entry, opener=None):
        """Private chat with a caller. `opener` is the already-generated
        first line of a knocker (see maybe_knock) — it goes straight into
        the chat and the history, making it clear that THEY opened the
        conversation."""
        term = self.term
        persona = entry["persona"]
        system = self._persona_system(persona)
        history = self.load_history(persona.handle)
        term.rule(t("users.chat_title", handle=persona.handle, node=entry["node"]))
        term.type_out(t("users.chat_connected"), delay=0.003)
        if opener:
            history.append({"role": "assistant", "content": opener})
            self.append_history(persona.handle, "assistant", opener)
            term.markdown(opener, prefix=f"{persona.handle}> ")
        try:
            while True:
                msg = term.prompt(t("users.chat_prompt"))
                if not msg or msg.lower() in ("exit", "quit", "q"):
                    term.type_out(t("users.chat_goodbye", handle=persona.handle), delay=0.003)
                    return
                history.append({"role": "user", "content": msg})
                reply = self.sysop.converse(system, history[-MAX_HISTORY:], max_tokens=500)
                if reply is None:
                    history.pop()
                    term.error(t("users.chat_no_reply", handle=persona.handle))
                    return
                history.append({"role": "assistant", "content": reply})
                # Write immediately — a crash mid-chat loses nothing.
                self.append_history(persona.handle, "user", msg)
                self.append_history(persona.handle, "assistant", reply)
                # Callers reply in Markdown; rich renders it in phosphor tone.
                term.markdown(reply, prefix=f"{persona.handle}> ")
        finally:
            term.rule()

    # -- Incoming chat requests ----------------------------------------

    def _opener_line(self, persona, history):
        """The first line of a knocker, written in character. The prior
        history is passed along as context so the line fits both the
        persona and the backstory — anyone who has written before picks
        up where they left off."""
        key = "users.opener_prompt_again" if history else "users.opener_prompt"
        return self.sysop.converse(
            self._persona_system(persona),
            list(history) + [{"role": "user", "content": t(key)}],
            max_tokens=200,
        )

    def maybe_knock(self):
        """Rolls whether someone is knocking right now. Called before the
        command prompt — not in the screensaver path, which stays untouched."""
        if not self.available():
            return
        now = time.monotonic()
        if now - self._last_knock < KNOCK_GAP:
            return
        if random.random() >= KNOCK_CHANCE:
            return
        # No on-demand generation for a knocker: whoever doesn't have a pool
        # yet isn't ambushed (and doesn't pay tokens for a random whim).
        entries = self.session_users(generate=False)
        if not entries:
            return
        self._last_knock = now
        entry = random.choice(entries)
        persona = entry["persona"]
        # The opening line is generated BEFORE the request: whoever is
        # knocking has already typed their message. Once accepted, it's
        # immediately in the chat — no AI wait after the 'y', and even with
        # existing history the knocker no longer stays silent.
        opener = self._opener_line(persona, self.load_history(persona.handle))
        if not opener:
            return   # AI returns nothing: then nobody knocks either
        self.term.beep()
        if self.term.confirm(t("users.knock", handle=persona.handle, node=entry["node"])):
            self.chat_with(entry, opener=opener)
        else:
            self.term.type_out(
                t("users.knock_declined", handle=persona.handle), delay=0.003
            )
