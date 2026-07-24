"""Menu value formatting kit — shared helpers for lightbar menus.

Small pure functions used to render and cycle row values in the config
menus (and any other lightbar menu that shows on/off, masked secrets,
status tags, or a value from a fixed sequence).
"""

from .i18n import t


def status_tag(status):
    return {"OK": "[ OK ]", "WARN": t("configmenu.status_warn"), "FEHLER": t("configmenu.status_error")}.get(
        status, "[????]"
    )


def mask(secret):
    return (secret[:10] + "…") if secret else t("configmenu.not_set")


def onoff(value):
    return t("configmenu.on") if value else t("configmenu.off")


def cycle(seq, current, direction):
    """Next value in a fixed sequence — forwards as well as backwards."""
    seq = list(seq)
    try:
        idx = seq.index(current)
    except ValueError:
        idx = 0
        direction = 0 if direction > 0 else direction
    return seq[(idx + direction) % len(seq)]
