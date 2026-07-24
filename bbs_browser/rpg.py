"""Shared skeleton for the two door games (dragon.py and space.py).

Both doors follow the same LORD-style frame: a persistent character with a
daily allowance, a turn-based fight loop, an upgrade counter, a caller-drawn
rival and a lightbar main menu. That frame lives here exactly once,
parameterised by a per-game config dict — every rule that actually differs
between forest and warp lane (monster stats, prices, locations, the boss
gates) stays in the game files.

A config dict provides:
    section         DB section name for the persistent state
    prefix          i18n key prefix ("dragon" / "space")
    fresh           () -> new state dict
    normalize       optional (state) -> None, run right after loading
    hp              state key for health ("hp" / "hull")
    energy          state key for the daily allowance ("fights" / "fuel")
    energy_per_day  daily allowance refill
    max_hp          (state) -> int, health ceiling
    attack          (state) -> int, attack power
    defense         (state) -> int, damage reduction
    currency        state key that is looted on a win and lost on death
    loot            foe keys credited on a win (also the spoils kwargs)
    flee_keys       combat keys that attempt an escape
    heal_key        combat key that uses a consumable
    heal_item       state key of the consumable ("potions" / "kits")
    heal_amount     health restored per consumable
    heal_kwarg      kwarg name of the restore message ("hp" / "hull")
    heal_missing    full i18n key: no consumable left
    heal_used       full i18n key: consumable used
    death_title / death_msg / death_hint    full i18n keys for defeat
    on_death        optional (state) -> None, extra losses on defeat
    stats           (term, state) -> None, the in-combat status sheet
    save            (state) -> None, persist and record
    shop            dict of full i18n keys for the upgrade counter:
                    owned, old, price, have_better, too_poor, bought,
                    title (with a {kind} placeholder), subtitle
"""

import random
from datetime import date

from . import lightbar
from .i18n import t
from .state import load_section


# -- Persistent state --------------------------------------------------------

def load_state(cfg):
    """Load the character and, if a day has passed since the last visit,
    open a new game day: the allowance is restored, the fallen rise again."""
    state = {**cfg["fresh"](), **(load_section(cfg["section"]) or {})}
    if cfg.get("normalize"):
        cfg["normalize"](state)
    today = date.today().isoformat()
    if state.get("day") != today:
        state["day"] = today
        state[cfg["energy"]] = cfg["energy_per_day"]
        state["alive"] = True
        state[cfg["hp"]] = cfg["max_hp"](state)
    state[cfg["hp"]] = min(state[cfg["hp"]], cfg["max_hp"](state))
    return state


def caller_handle():
    """A random caller from the persona pool in users.py — (handle, seed),
    so the same caller is always equally strong. Without a pool (no AI key,
    nobody ever online) there is no rival: None."""
    pool = (load_section("users") or {}).get("pool") or []
    handles = [str(p.get("handle", "")).strip() for p in pool if isinstance(p, dict)]
    handles = [h for h in handles if h]
    if not handles:
        return None
    handle = random.choice(handles)
    return handle, sum(ord(c) for c in handle)


# -- Combat ------------------------------------------------------------------

def bar(term, cfg, state, foe):
    term.type_out(
        t(f"{cfg['prefix']}.combat_status", you=state[cfg["hp"]],
          max=cfg["max_hp"](state), foe=foe["name"], foe_hp=max(foe["hp"], 0)),
        delay=0)


def fight(term, cfg, state, foe, can_flee=True):
    """A fight until it's decided. Returns 'win', 'flee', or 'dead'."""
    p = cfg["prefix"]
    term.rule(t(f"{p}.combat_title", foe=foe["name"]))
    term.type_out(t(f"{p}.combat_intro", foe=foe["name"]), delay=0.004)
    while True:
        bar(term, cfg, state, foe)
        choice = (term.prompt(t(f"{p}.combat_prompt")) or "").strip().lower()[:1]
        if choice in cfg["flee_keys"] and can_flee:
            if random.random() < 0.55:
                term.type_out(t(f"{p}.flee_ok"), delay=0.004)
                return "flee"
            term.type_out(t(f"{p}.flee_fail"), delay=0.004)
        elif choice in cfg["flee_keys"]:
            term.type_out(t(f"{p}.flee_blocked"), delay=0.004)
            continue
        elif choice == cfg["heal_key"]:
            if state[cfg["heal_item"]] <= 0:
                term.type_out(t(cfg["heal_missing"]), delay=0.003)
                continue
            state[cfg["heal_item"]] -= 1
            healed = min(cfg["heal_amount"], cfg["max_hp"](state) - state[cfg["hp"]])
            state[cfg["hp"]] += healed
            term.type_out(t(cfg["heal_used"], left=state[cfg["heal_item"]],
                            **{cfg["heal_kwarg"]: healed}), delay=0.004)
        elif choice == "s":
            cfg["stats"](term, state)
            continue
        else:
            # Everything else is an attack — when in doubt, strike.
            power = cfg["attack"](state)
            dmg = random.randint(power // 2, power) + 1
            crit = random.random() < 0.12
            if crit:
                dmg *= 2
            foe["hp"] -= dmg
            term.type_out(
                t(f"{p}.hit_crit" if crit else f"{p}.hit", foe=foe["name"], dmg=dmg),
                delay=0.004)
            if foe["hp"] <= 0:
                term.type_out(t(f"{p}.foe_down", foe=foe["name"]), delay=0.005)
                term.beep()
                return "win"

        back = max(1, random.randint(foe["dmg"] // 2, foe["dmg"])
                   - cfg["defense"](state) // 2)
        state[cfg["hp"]] -= back
        term.type_out(t(f"{p}.foe_hit", foe=foe["name"], dmg=back), delay=0.004)
        if state[cfg["hp"]] <= 0:
            state[cfg["hp"]] = 0
            return "dead"


def died(term, cfg, state, foe):
    """Defeat: the day is over, cash on hand is gone — the bank survives."""
    state["alive"] = False
    state["deaths"] += 1
    lost, state[cfg["currency"]] = state[cfg["currency"]], 0
    if cfg.get("on_death"):
        cfg["on_death"](state)
    state[cfg["energy"]] = 0
    cfg["save"](state)
    term.rule(t(cfg["death_title"]))
    term.type_out(t(cfg["death_msg"], foe=foe["name"], **{cfg["currency"]: lost}),
                  delay=0.005)
    term.type_out(t(cfg["death_hint"]), delay=0.003)
    term.beep(2)
    term.pause()


def won(term, cfg, state, foe):
    for key in cfg["loot"]:
        state[key] += foe[key]
    state["kills"] += 1
    if foe.get("caller"):
        state["duels"] += 1
    term.type_out(t(f"{cfg['prefix']}.spoils", **{k: foe[k] for k in cfg["loot"]}),
                  delay=0.004)
    cfg["save"](state)
    term.pause()


# -- The upgrade counter -----------------------------------------------------

def shop(term, cfg, state, kind, table, slot, after_buy=None):
    """One counter, one goods basket: a (price, power) table for one
    equipment slot. `after_buy` runs before saving, for game-specific
    side effects of a purchase."""
    keys = cfg["shop"]
    cur = cfg["currency"]

    def rows():
        out = []
        for i, (price, power) in enumerate(table):
            name = t(f"{cfg['prefix']}.{kind}_{i}")
            if i == state[slot]:
                value = t(keys["owned"])
            elif i < state[slot]:
                value = t(keys["old"])
            else:
                value = t(keys["price"], price=price, power=power)
            out.append((str(i + 1), name, value))
        return out

    while True:
        choice = lightbar.menu(
            term, t(keys["title"].format(kind=kind)), rows,
            subtitle=t(keys["subtitle"], **{cur: state[cur]}))
        if not choice or not choice.isdigit():
            return
        idx = int(choice) - 1
        if not 0 <= idx < len(table):
            continue
        price = table[idx][0]
        if idx <= state[slot]:
            term.type_out(t(keys["have_better"]), delay=0.003)
            continue
        if state[cur] < price:
            term.type_out(t(keys["too_poor"], missing=price - state[cur]), delay=0.004)
            continue
        state[cur] -= price
        state[slot] = idx
        if after_buy:
            after_buy(state, slot)
        cfg["save"](state)
        term.type_out(t(keys["bought"], name=t(f"{cfg['prefix']}.{kind}_{idx}")),
                      delay=0.004)


# -- The main menu -----------------------------------------------------------

def run_loop(term, cfg, state, rows, subtitle, actions):
    """Entry frame from the arcade: title, welcome, and the lightbar loop.
    `actions` maps menu keys to (term, state) callables."""
    p = cfg["prefix"]
    term.rule(t(f"{p}.title"))
    term.type_out(t(f"{p}.welcome"), delay=0.005)
    at = "1"
    while True:
        choice = lightbar.menu(term, t(f"{p}.title"), rows,
                               subtitle=subtitle(), start=at)
        if not choice or choice in ("q", "0"):
            cfg["save"](state)
            return
        at = choice
        action = actions.get(choice)
        if action is not None:
            action(term, state)
        else:
            term.error(t(f"{p}.unknown_choice"))
