"""The 'log' command — review and delete saved chat histories.

The history itself lives in db.chat_log; this module only handles
the display."""

import time

from . import db
from .i18n import t


def _label(channel):
    """Translates 'sysop' and 'user:HANDLE' into something readable.
    A title assigned by the SysOp takes precedence."""
    title = db.chat_title(channel)
    if title:
        return title
    if channel == "sysop":
        return t("chatlog.channel_sysop")
    if channel.startswith("user:"):
        return channel[5:]
    return channel


def _when(ts):
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return "?"


def run(term, arg="", browser=None):
    """Entry point from navigation.py.
    Syntax: log | log <nr> | log <nr> chat | log del <nr> | log clear."""
    arg = (arg or "").strip()
    parts = arg.split()
    verb = parts[0].lower() if parts else ""

    if verb == "clear":
        db.chat_clear()
        term.type_out(t("chatlog.cleared_all"), delay=0.003)
        return

    channels = db.chat_channels()
    if not channels:
        term.type_out(t("chatlog.empty"), delay=0.003)
        return

    if verb in ("del", "loesch", "delete"):
        entry = _pick(term, channels, parts[1] if len(parts) > 1 else "")
        if entry:
            db.chat_clear(entry["channel"])
            term.type_out(t("chatlog.cleared_one", name=_label(entry["channel"])), delay=0.003)
        return

    if not verb:
        _list(term, channels)
        return

    entry = _pick(term, channels, verb)
    if not entry:
        return
    # 'log <nr> chat' re-enters exactly this history.
    if len(parts) > 1 and parts[1].lower() in ("chat", "weiter", "resume"):
        _resume(term, browser, entry["channel"])
        return
    _show(term, entry["channel"])


def resume_by_number(term, browser, raw):
    """Entry point from 'chat <nr>': resumes the history with this list number."""
    channels = db.chat_channels()
    if not channels:
        term.type_out(t("chatlog.empty"), delay=0.003)
        return
    entry = _pick(term, channels, raw)
    if entry:
        _resume(term, browser, entry["channel"])


def _resume(term, browser, channel):
    """Resumes the saved history — with the SysOp or with the caller."""
    if channel == "sysop":
        if not browser or not browser.sysop:
            term.error(t("chatlog.resume_unavailable"))
            return
        browser.sysop.chat()
        return
    if channel.startswith("user:"):
        if not browser or not browser.users:
            term.error(t("chatlog.resume_unavailable"))
            return
        browser.users.resume_chat(channel[5:])
        return
    term.error(t("chatlog.resume_unavailable"))


def _pick(term, channels, raw):
    """Selects a channel by its list number."""
    if not raw.isdigit():
        term.error(t("chatlog.usage"))
        return None
    num = int(raw)
    if not 1 <= num <= len(channels):
        term.error(t("chatlog.error_bad_number", num=num))
        return None
    return channels[num - 1]


def _list(term, channels):
    term.rule(t("chatlog.title"))
    for i, entry in enumerate(channels, 1):
        term.type_out(
            t("chatlog.line", num=i, name=_label(entry["channel"]),
              count=entry["count"], when=_when(entry["last"])),
            delay=0.001,
        )
    term.type_out("", delay=0)
    term.type_out(t("chatlog.usage"), delay=0.001)
    term.rule()


def _show(term, channel):
    lines = db.chat_transcript(channel, limit=50)
    term.rule(t("chatlog.transcript_title", name=_label(channel)))
    for line in lines:
        who = t("chatlog.you") if line["role"] == "user" else _label(channel)
        term.type_out(f"[{_when(line['ts'])}] {who}:", delay=0.001)
        term.markdown(line["text"])
    term.rule()
