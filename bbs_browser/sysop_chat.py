"""Multi-chat session management for the AI SysOp.

Several conversations exist side by side (channels "sysop", "sysop:2", ...);
the board picks one, slash commands manage them, and the transcript tail
makes resuming feel like picking up the thread. The functions take the
SysOp instance as their first parameter; SysOp keeps thin delegating
methods so the public surface (browser, navigation, chatlog, tests)
stays unchanged.
"""

from . import db
from .i18n import t

CHAT_CHANNEL = "sysop"   # channel prefix of the SysOp chats in history
CHAT_TITLE_MAX = 40      # a chat title never grows past this
REPLAY_LINES = 6         # transcript lines shown when re-entering a chat


def _chat_when(ts):
    """Short timestamp for the chat board."""
    import time
    try:
        return time.strftime("%d.%m. %H:%M", time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return "?"


def chat_label(sysop, channel=None):
    """Display name of a chat: its title, else 'SYSOP' / 'SYSOP #N'."""
    channel = channel or sysop.chat_channel
    title = db.chat_title(channel)
    if title:
        return title
    if channel == CHAT_CHANNEL:
        return t("chatlog.channel_sysop")
    return t("chatlog.channel_sysop_n", num=channel.rsplit(":", 1)[-1])


def switch_chat(sysop, channel):
    """Makes `channel` the active conversation and loads its history."""
    sysop.chat_channel = channel
    sysop.chat_history = db.chat_history(channel, limit=20)
    sysop._chat_ctx_url = None
    db.set_active_chat(channel)


def new_chat(sysop):
    """Opens a fresh conversation. The base channel is reused as long
    as it has never been written to."""
    if not db.chat_history(CHAT_CHANNEL, limit=1) and not db.chat_title(CHAT_CHANNEL):
        switch_chat(sysop, CHAT_CHANNEL)
    else:
        switch_chat(sysop, db.new_chat_channel(CHAT_CHANNEL))
    return sysop.chat_channel


def chat_board(sysop):
    """The 'chat' command: pick a conversation from the board, then talk.
    With no stored chats it jumps straight into the first one."""
    if db.chat_channels(prefix=CHAT_CHANNEL):
        picked = pick_chat(sysop)
        if not picked:
            return
        if picked == "new":
            new_chat(sysop)
        else:
            switch_chat(sysop, picked)
    chat(sysop)


def pick_chat(sysop):
    """Lightbar board of all SysOp chats. Returns a channel, 'new',
    or None for back. 'x' deletes the highlighted conversation."""
    from . import lightbar
    term = sysop.term

    def entries():
        return db.chat_channels(prefix=CHAT_CHANNEL)

    def rows():
        out = []
        for i, e in enumerate(entries(), 1):
            marker = "» " if e["channel"] == sysop.chat_channel else "  "
            label = (marker + chat_label(sysop, e["channel"]))[:34]
            out.append((str(i), label, t(
                "sysop.board_line", count=e["count"],
                when=_chat_when(e["last"]))))
        out.append((None, "", ""))
        out.append(("n", t("sysop.board_new"), ""))
        return out

    def on_key(pressed, key):
        if pressed not in ("x", "X") or not key or not key.isdigit():
            return False
        listing = entries()
        idx = int(key) - 1
        if not 0 <= idx < len(listing):
            return False
        channel = listing[idx]["channel"]
        db.chat_clear(channel)
        if channel == sysop.chat_channel:
            switch_chat(sysop, CHAT_CHANNEL)
        return True

    choice = lightbar.menu(
        term, t("sysop.board_title"), rows,
        on_key=on_key, hint=t("sysop.board_hint"), page_size=14,
    )
    if choice == lightbar.BACK:
        return None
    if choice == "n":
        return "new"
    listing = entries()
    if choice.isdigit() and 1 <= int(choice) <= len(listing):
        return listing[int(choice) - 1]["channel"]
    return None


def chat_divider(sysop):
    """Dotted line between chat exchanges — keeps the transcript scannable."""
    from .constants import DIM, RESET, screen_width
    sysop.term.type_out(DIM + "┄" * screen_width() + RESET, delay=0)


def replay_tail(sysop):
    """A few lines of the stored conversation, dimmed — so resuming a
    chat feels like picking up the thread, not starting over."""
    from .constants import DIM, RESET
    lines = db.chat_transcript(sysop.chat_channel, limit=REPLAY_LINES)
    if not lines:
        return
    you, name = t("sysop.chat_prompt").strip(), t("sysop.chat_reply_prefix").strip()
    for line in lines:
        who = you if line["role"] == "user" else name
        text = " ".join((line["text"] or "").split())[:200]
        sysop.term.type_out(DIM + f"{who} {text}" + RESET, delay=0.0005)
    chat_divider(sysop)


def auto_title(sysop, question, reply):
    """Names an untitled chat after the first exchange — one cheap
    completion; failures stay silent."""
    try:
        text = sysop._raw_complete(
            t("sysop.title_system"),
            [{"role": "user",
              "content": f"{question}\n---\n{(reply or '')[:600]}"}],
            30,
        )
    except Exception:
        return
    lines = (text or "").strip().strip('"\'').splitlines()
    title = lines[0][:CHAT_TITLE_MAX].strip() if lines else ""
    if title:
        db.chat_set_title(sysop.chat_channel, title)
        sysop.term.type_out(t("sysop.chat_titled", title=title), delay=0.002)


def chat_command(sysop, msg):
    """Slash commands inside the chat. Returns 'handled', 'board', or None."""
    low = msg.lower()
    if low in ("/neu", "/new"):
        new_chat(sysop)
        sysop.term.type_out(t("sysop.chat_new_started"), delay=0.003)
        return "handled"
    if low in ("/chats", "/menu", "/board"):
        return "board"
    if low.startswith("/name"):
        title = msg[5:].strip()[:CHAT_TITLE_MAX]
        db.chat_set_title(sysop.chat_channel, title)
        sysop.term.type_out(
            t("sysop.chat_renamed", title=title) if title
            else t("sysop.chat_rename_cleared"), delay=0.003)
        return "handled"
    if low.startswith("/"):
        sysop.term.type_out(t("sysop.chat_commands"), delay=0.003)
        return "handled"
    return None


def chat(sysop, channel=None):
    """Interactive chat with the SysOp. Empty input or 'exit' ends it;
    /neu, /chats and /name manage the conversations."""
    if channel and channel != sysop.chat_channel:
        switch_chat(sysop, channel)
    while True:
        result = chat_session(sysop)
        if result != "board":
            return
        picked = pick_chat(sysop)
        if not picked:
            return
        if picked == "new":
            new_chat(sysop)
        else:
            switch_chat(sysop, picked)


def chat_session(sysop):
    """One stretch of conversation in the active channel. Returns
    'board' when the caller asked for the chat board, else None."""
    term = sysop.term
    if not sysop.client():
        return None
    from .constants import DIM, RESET
    term.rule(t("sysop.chat_title_named", name=chat_label(sysop)))
    replay_tail(sysop)
    term.type_out(t("sysop.chat_connected"), delay=0.003)
    term.type_out(DIM + t("sysop.chat_commands") + RESET, delay=0.0005)
    while True:
        msg = term.prompt(t("sysop.chat_prompt"))
        if not msg or msg.lower() in ("exit", "quit", "q"):
            term.type_out(t("sysop.chat_goodbye"), delay=0.003)
            term.rule()
            return None
        handled = chat_command(sysop, msg)
        if handled == "board":
            term.rule()
            return "board"
        if handled == "handled":
            # A command may have switched the channel — reprint the header.
            term.rule(t("sysop.chat_title_named", name=chat_label(sysop)))
            continue
        # Provide the current page as context once (and again as
        # soon as the caller has a different page on screen).
        instruction = msg
        page = sysop.browser.page if sysop.browser else None
        if page and page.url != sysop._chat_ctx_url:
            sysop._chat_ctx_url = page.url
            ctx = sysop._page_text(page)[:6000]
            instruction = (
                f"[Kontext — diese Seite hat der Anrufer gerade auf dem Schirm:]\n"
                f"{ctx}\n[Ende Kontext]\n\nAnrufer: {msg}"
            )
        reply = sysop.run(
            instruction, history=sysop.chat_history[-20:], max_tokens=800, quiet=True,
        )
        if reply is None:
            # Empty reply (e.g. only tool rounds with no final text) doesn't
            # end the whole session — wait for the next question.
            term.error(t("sysop.chat_no_reply"))
            continue
        # Save with context, so the page stays known for follow-up questions;
        # for review ('log') `display` holds just the plain question.
        sysop.chat_history.append({"role": "user", "content": instruction})
        sysop.chat_history.append({"role": "assistant", "content": reply})
        db.chat_append(sysop.chat_channel, "user", instruction, display=msg)
        db.chat_append(sysop.chat_channel, "assistant", reply)
        # First full exchange in an untitled chat: let the AI name it,
        # the way every modern chat client does — but only once.
        if sysop.chat_channel not in sysop._titled and not db.chat_title(sysop.chat_channel):
            sysop._titled.add(sysop.chat_channel)
            auto_title(sysop, msg, reply)
        chat_divider(sysop)
