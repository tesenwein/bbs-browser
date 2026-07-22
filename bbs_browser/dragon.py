"""Door game 'The Ancient Wyrm' — the mailbox's role-playing game.

A door game in the spirit of the classics that hung on every BBS in the
90s: a limited number of forest fights per day, buying weapons in between,
healing at the tavern, leveling up with the master — and eventually, at
level 12, facing off against the Ancient Wyrm.

The character lives in the "dragon" section of the database and survives
hanging up. Fights against other callers use the persona pool from
users.py: whoever has been online on the mailbox can be run into in the
forest.

Unlike Paddle and Stacker, this game doesn't need a raw terminal — it's a
text door like back in the day, so it also works through a pipe.
"""

import random
from datetime import date

from . import lightbar
from .i18n import t
from .state import load_section, save_section

SECTION = "dragon"
FIGHTS_PER_DAY = 15
MAX_LEVEL = 12
POTION_PRICE = 25
POTION_HEAL = 20

# (price, damage) — the name is stored as 'dragon.weapon_<n>' in the catalog.
WEAPONS = [(0, 6), (200, 11), (800, 18), (3000, 28), (10000, 42), (40000, 60)]
# (price, armor)
ARMORS = [(0, 0), (150, 3), (700, 7), (2800, 12), (9000, 20), (35000, 30)]

# Experience the master wants to see for the next rank.
EXP_NEEDED = [0, 100, 400, 1000, 2500, 5000, 10000, 20000,
              40000, 80000, 150000, 300000]

DRAGON_HP = 600
DRAGON_DMG = 45


# -- Character -------------------------------------------------------------

def _fresh():
    return {
        "level": 1, "exp": 0, "hp": 25, "gold": 0, "bank": 0,
        "weapon": 0, "armor": 0, "potions": 1,
        "fights": FIGHTS_PER_DAY, "day": "", "alive": True,
        "kills": 0, "deaths": 0, "duels": 0, "slain": 0,
    }


def max_hp(hero):
    return 25 + (hero["level"] - 1) * 16


def attack_power(hero):
    return WEAPONS[hero["weapon"]][1] + hero["level"] * 3


def defense(hero):
    return ARMORS[hero["armor"]][1]


def load_hero():
    """Load the character and, if a day has passed since the last visit,
    open a new game day: fights are restored, the fallen rise again."""
    hero = {**_fresh(), **(load_section(SECTION) or {})}
    today = date.today().isoformat()
    if hero.get("day") != today:
        hero["day"] = today
        hero["fights"] = FIGHTS_PER_DAY
        hero["alive"] = True
        hero["hp"] = max_hp(hero)
    hero["hp"] = min(hero["hp"], max_hp(hero))
    return hero


def save_hero(hero):
    save_section(SECTION, hero)
    _record(hero)


def _record(hero):
    """The arcade shows one number per game — here the highest rank reached."""
    games = load_section("games")
    if hero["level"] > int(games.get("dragon", games.get("drache", 0))):
        games["dragon"] = hero["level"]
        save_section("games", games)


# -- Enemies ----------------------------------------------------------------

def _pick(key):
    """A random entry from a '|'-separated catalog line."""
    return random.choice(t(key).split("|"))


def monster_for(level):
    """A forest dweller matching the rank — name rolled, stats scaled."""
    bases = t("dragon.monster_bases").split("|")
    name = f"{_pick('dragon.monster_prefixes')} {bases[min(level, len(bases)) - 1]}"
    return {
        "name": name,
        "hp": 10 + level * 9 + random.randint(0, level * 4),
        "dmg": 2 + level * 2,
        "gold": level * 18 + random.randint(0, level * 10),
        "exp": level * 14 + random.randint(0, level * 6),
    }


def master_for(level):
    masters = t("dragon.masters").split("|")
    return {
        "name": masters[min(level, len(masters)) - 1],
        "hp": 25 + level * 22,
        "dmg": 3 + int(level * 2.5),
        "gold": 0,
        "exp": 0,
    }


def _caller_foe(level):
    """Another caller as an opponent — the personas from users.py. Without a
    pool (no AI key, nobody ever online) there is no duel opponent."""
    pool = (load_section("users") or {}).get("pool") or []
    handles = [str(p.get("handle", "")).strip() for p in pool if isinstance(p, dict)]
    handles = [h for h in handles if h]
    if not handles:
        return None
    handle = random.choice(handles)
    # Derive stats from the handle: the same caller is always equally strong.
    seed = sum(ord(c) for c in handle)
    return {
        "name": handle,
        "hp": 20 + level * 11 + seed % 30,
        "dmg": 3 + int(level * 2.0) + seed % 4,
        "gold": level * 30 + seed % 60,
        "exp": level * 20,
        "caller": True,
    }


# -- Combat -----------------------------------------------------------------

def _bar(term, hero, foe):
    term.type_out(
        t("dragon.combat_status", you=hero["hp"], max=max_hp(hero),
          foe=foe["name"], foe_hp=max(foe["hp"], 0)), delay=0)


def fight(term, hero, foe, can_flee=True):
    """A fight until it's decided. Returns 'win', 'flee', or 'dead'."""
    term.rule(t("dragon.combat_title", foe=foe["name"]))
    term.type_out(t("dragon.combat_intro", foe=foe["name"]), delay=0.004)
    while True:
        _bar(term, hero, foe)
        choice = (term.prompt(t("dragon.combat_prompt")) or "").strip().lower()[:1]
        if choice in ("f", "l") and can_flee:
            if random.random() < 0.55:
                term.type_out(t("dragon.flee_ok"), delay=0.004)
                return "flee"
            term.type_out(t("dragon.flee_fail"), delay=0.004)
        elif choice in ("f", "l"):
            term.type_out(t("dragon.flee_blocked"), delay=0.004)
            continue
        elif choice == "h":
            if hero["potions"] <= 0:
                term.type_out(t("dragon.no_potion"), delay=0.003)
                continue
            hero["potions"] -= 1
            healed = min(POTION_HEAL, max_hp(hero) - hero["hp"])
            hero["hp"] += healed
            term.type_out(t("dragon.potion_used", hp=healed, left=hero["potions"]), delay=0.004)
        elif choice == "s":
            show_stats(term, hero)
            continue
        else:
            # Everything else is an attack — when in doubt, strike.
            dmg = random.randint(attack_power(hero) // 2, attack_power(hero)) + 1
            crit = random.random() < 0.12
            if crit:
                dmg *= 2
            foe["hp"] -= dmg
            term.type_out(
                t("dragon.hit_crit" if crit else "dragon.hit", foe=foe["name"], dmg=dmg),
                delay=0.004)
            if foe["hp"] <= 0:
                term.type_out(t("dragon.foe_down", foe=foe["name"]), delay=0.005)
                term.beep()
                return "win"

        back = max(1, random.randint(foe["dmg"] // 2, foe["dmg"]) - defense(hero) // 2)
        hero["hp"] -= back
        term.type_out(t("dragon.foe_hit", foe=foe["name"], dmg=back), delay=0.004)
        if hero["hp"] <= 0:
            hero["hp"] = 0
            return "dead"


def _died(term, hero, foe):
    hero["alive"] = False
    hero["deaths"] += 1
    lost, hero["gold"] = hero["gold"], 0
    hero["fights"] = 0
    save_hero(hero)
    term.rule(t("dragon.dead_title"))
    term.type_out(t("dragon.dead_msg", foe=foe["name"], gold=lost), delay=0.005)
    term.type_out(t("dragon.dead_hint"), delay=0.003)
    term.beep(2)
    term.pause()


def _won(term, hero, foe):
    hero["gold"] += foe["gold"]
    hero["exp"] += foe["exp"]
    hero["kills"] += 1
    if foe.get("caller"):
        hero["duels"] += 1
    term.type_out(t("dragon.spoils", gold=foe["gold"], exp=foe["exp"]), delay=0.004)
    save_hero(hero)
    term.pause()


# -- The locations --------------------------------------------------------------

def forest(term, hero):
    if not hero["alive"]:
        term.error(t("dragon.you_are_dead"))
        term.pause()
        return
    if hero["fights"] <= 0:
        term.error(t("dragon.no_fights_left"))
        term.pause()
        return
    hero["fights"] -= 1
    foe = _caller_foe(hero["level"]) if random.random() < 0.2 else None
    if foe:
        term.type_out(t("dragon.caller_encounter", handle=foe["name"]), delay=0.005)
    else:
        foe = monster_for(hero["level"])
    outcome = fight(term, hero, foe)
    if outcome == "win":
        _won(term, hero, foe)
    elif outcome == "dead":
        _died(term, hero, foe)
    else:
        save_hero(hero)


def master(term, hero):
    """You level up with the master — but you have to beat him first."""
    if hero["level"] >= MAX_LEVEL:
        term.type_out(t("dragon.master_topped"), delay=0.004)
        term.pause()
        return
    need = EXP_NEEDED[hero["level"]]
    if hero["exp"] < need:
        term.type_out(t("dragon.master_not_yet", need=need - hero["exp"]), delay=0.004)
        term.pause()
        return
    if not hero["alive"]:
        term.error(t("dragon.you_are_dead"))
        term.pause()
        return
    foe = master_for(hero["level"])
    term.type_out(t("dragon.master_challenge", master=foe["name"]), delay=0.005)
    outcome = fight(term, hero, foe, can_flee=False)
    if outcome == "dead":
        _died(term, hero, foe)
        return
    hero["level"] += 1
    hero["hp"] = max_hp(hero)
    term.rule(t("dragon.level_up_title"))
    term.type_out(t("dragon.level_up", level=hero["level"], hp=max_hp(hero)), delay=0.005)
    term.beep(2)
    save_hero(hero)
    term.pause()


def _shop(term, hero, kind):
    """Weapon and armor shop — same counter, two goods baskets."""
    table = WEAPONS if kind == "weapon" else ARMORS
    slot = "weapon" if kind == "weapon" else "armor"

    def rows():
        out = []
        for i, (price, power) in enumerate(table):
            name = t(f"dragon.{kind}_{i}")
            if i == hero[slot]:
                value = t("dragon.shop_owned")
            elif i < hero[slot]:
                value = t("dragon.shop_old")
            else:
                value = t("dragon.shop_price", price=price, power=power)
            out.append((str(i + 1), name, value))
        return out

    while True:
        choice = lightbar.menu(
            term, t(f"dragon.shop_title_{kind}"), rows,
            subtitle=t("dragon.shop_subtitle", gold=hero["gold"]))
        if not choice or not choice.isdigit():
            return
        idx = int(choice) - 1
        if not 0 <= idx < len(table):
            continue
        price = table[idx][0]
        if idx <= hero[slot]:
            term.type_out(t("dragon.shop_have_better"), delay=0.003)
            continue
        if hero["gold"] < price:
            term.type_out(t("dragon.shop_too_poor", missing=price - hero["gold"]), delay=0.004)
            continue
        hero["gold"] -= price
        hero[slot] = idx
        save_hero(hero)
        term.type_out(t("dragon.shop_bought", name=t(f"dragon.{kind}_{idx}")), delay=0.004)


def tavern(term, hero):
    """Tavern: heal, buy potions, deposit gold in the chest."""
    def rows():
        return [
            ("1", t("dragon.tavern_heal"), t("dragon.tavern_heal_value",
                                             hp=max_hp(hero) - hero["hp"],
                                             price=(max_hp(hero) - hero["hp"]) * 2)),
            ("2", t("dragon.tavern_potion"), t("dragon.tavern_potion_value",
                                               price=POTION_PRICE, have=hero["potions"])),
            ("3", t("dragon.tavern_deposit"), t("dragon.tavern_bank_value", bank=hero["bank"])),
            ("4", t("dragon.tavern_withdraw"), t("dragon.tavern_bank_value", bank=hero["bank"])),
        ]

    while True:
        choice = lightbar.menu(term, t("dragon.tavern_title"), rows,
                               subtitle=t("dragon.shop_subtitle", gold=hero["gold"]))
        if not choice:
            return
        if choice == "1":
            missing = max_hp(hero) - hero["hp"]
            if missing <= 0:
                term.type_out(t("dragon.tavern_fit"), delay=0.003)
                continue
            price = missing * 2
            if hero["gold"] < price:
                # Heal as much as the gold allows — nobody leaves empty-handed.
                missing = hero["gold"] // 2
                price = missing * 2
            if missing <= 0:
                term.type_out(t("dragon.shop_too_poor", missing=2 - hero["gold"]), delay=0.004)
                continue
            hero["gold"] -= price
            hero["hp"] += missing
            save_hero(hero)
            term.type_out(t("dragon.tavern_healed", hp=missing, price=price), delay=0.004)
        elif choice == "2":
            if hero["gold"] < POTION_PRICE:
                term.type_out(t("dragon.shop_too_poor", missing=POTION_PRICE - hero["gold"]), delay=0.004)
                continue
            hero["gold"] -= POTION_PRICE
            hero["potions"] += 1
            save_hero(hero)
            term.type_out(t("dragon.tavern_potion_bought", have=hero["potions"]), delay=0.004)
        elif choice in ("3", "4"):
            amount = (term.prompt(t("dragon.tavern_amount")) or "").strip()
            if not amount.isdigit():
                continue
            amount = int(amount)
            if choice == "3":
                amount = min(amount, hero["gold"])
                hero["gold"] -= amount
                hero["bank"] += amount
            else:
                amount = min(amount, hero["bank"])
                hero["bank"] -= amount
                hero["gold"] += amount
            save_hero(hero)
            term.type_out(t("dragon.tavern_bank_ok", gold=hero["gold"], bank=hero["bank"]), delay=0.004)


def red_dragon(term, hero):
    """The final battle. Whoever wins starts over, ennobled."""
    if hero["level"] < MAX_LEVEL:
        term.type_out(t("dragon.dragon_too_weak", level=MAX_LEVEL), delay=0.004)
        term.pause()
        return
    if not hero["alive"]:
        term.error(t("dragon.you_are_dead"))
        term.pause()
        return
    term.rule(t("dragon.dragon_title"))
    term.type_out(t("dragon.dragon_intro"), delay=0.006)
    foe = {"name": t("dragon.dragon_name"), "hp": DRAGON_HP, "dmg": DRAGON_DMG,
           "gold": 0, "exp": 0}
    if fight(term, hero, foe, can_flee=False) == "dead":
        _died(term, hero, foe)
        return
    hero["slain"] += 1
    term.rule(t("dragon.dragon_won_title"))
    term.type_out(t("dragon.dragon_won", times=hero["slain"]), delay=0.006)
    term.beep(3)
    # New run: stats reset, glory remains.
    keep = {k: hero[k] for k in ("kills", "deaths", "duels", "slain", "day")}
    hero.update(_fresh())
    hero.update(keep)
    hero["hp"] = max_hp(hero)
    save_hero(hero)
    term.pause()


def show_stats(term, hero):
    handle = (load_section("profile") or {}).get("handle", "GAST")
    term.rule(t("dragon.stats_title", handle=handle))
    term.box([
        f"{label:<22}{value}" for label, value in (
            (t("dragon.stat_level"), f"{hero['level']} / {MAX_LEVEL}"),
            (t("dragon.stat_hp"), f"{hero['hp']} / {max_hp(hero)}"),
            (t("dragon.stat_exp"), _exp_line(hero)),
            (t("dragon.stat_weapon"), t(f"dragon.weapon_{hero['weapon']}")),
            (t("dragon.stat_armor"), t(f"dragon.armor_{hero['armor']}")),
            (t("dragon.stat_gold"), f"{hero['gold']}  ({t('dragon.stat_bank')}: {hero['bank']})"),
            (t("dragon.stat_potions"), str(hero["potions"])),
            (t("dragon.stat_fights"), str(hero["fights"])),
            (t("dragon.stat_kills"), f"{hero['kills']}  ({t('dragon.stat_duels')}: {hero['duels']})"),
            (t("dragon.stat_slain"), str(hero["slain"])),
        )])
    term.pause()


def _exp_line(hero):
    if hero["level"] >= MAX_LEVEL:
        return str(hero["exp"])
    return t("dragon.exp_of", exp=hero["exp"], need=EXP_NEEDED[hero["level"]])


# -- The village square ---------------------------------------------------------

def run(term):
    """Entry point from the arcade: the village square with all locations."""
    hero = load_hero()
    save_hero(hero)
    term.rule(t("dragon.title"))
    term.type_out(t("dragon.welcome"), delay=0.005)

    def rows():
        state = t("dragon.state_dead") if not hero["alive"] else \
            t("dragon.state_alive", hp=hero["hp"], max=max_hp(hero))
        return [
            (None, t("dragon.head_place"), ""),
            ("1", t("dragon.menu_forest"), t("dragon.menu_forest_value", n=hero["fights"])),
            ("2", t("dragon.menu_master"), _exp_line(hero)),
            ("3", t("dragon.menu_dragon"), t("dragon.menu_dragon_value")),
            (None, t("dragon.head_town"), ""),
            ("4", t("dragon.menu_weapons"), t(f"dragon.weapon_{hero['weapon']}")),
            ("5", t("dragon.menu_armor"), t(f"dragon.armor_{hero['armor']}")),
            ("6", t("dragon.menu_tavern"), t("dragon.menu_tavern_value", gold=hero["gold"])),
            ("7", t("dragon.menu_stats"), state),
        ]

    at = "1"
    while True:
        choice = lightbar.menu(term, t("dragon.title"), rows,
                               subtitle=t("dragon.menu_subtitle",
                                          level=hero["level"], gold=hero["gold"]),
                               start=at)
        if not choice or choice in ("q", "0"):
            save_hero(hero)
            return
        at = choice
        if choice == "1":
            forest(term, hero)
        elif choice == "2":
            master(term, hero)
        elif choice == "3":
            red_dragon(term, hero)
        elif choice == "4":
            _shop(term, hero, "weapon")
        elif choice == "5":
            _shop(term, hero, "armor")
        elif choice == "6":
            tavern(term, hero)
        elif choice == "7":
            show_stats(term, hero)
        else:
            term.error(t("dragon.unknown_choice"))
