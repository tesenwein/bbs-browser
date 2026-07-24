"""Door game 'Sternenkurier' — the mailbox's space trading door.

A trading door in the spirit of the genre that ran on the big boards:
a galaxy of twelve sectors, each with its own trade post and its own
prices, a limited fuel supply per day, pirates on the warp lanes — and
somewhere out in the wreck field waits the Hollow Colossus.

Everything here is original: sectors, goods, ships and the colossus are
this mailbox's own lore, not borrowed from any commercial door.

The ship lives in the "space" section of the database and survives
hanging up. Pirate captains are drawn from the persona pool in users.py:
whoever has been online on the mailbox can jump your freighter.

Like dragon.py this is a plain text door — no raw terminal needed, so it
also works through a pipe.
"""

import random
from datetime import date

from . import lightbar
from .i18n import t
from .state import load_section, save_section

SECTION = "space"
SECTORS = 12
WARPS_PER_DAY = 20
BOSS_SECTOR = SECTORS
BOSS_MIN_LASER = 4
KIT_PRICE = 80
KIT_REPAIR = 25

GOODS = ("ore", "isotopes", "circuits")
BASE_PRICE = {"ore": 22, "isotopes": 55, "circuits": 120}

# (price, damage) — the name is stored as 'space.laser_<n>' in the catalog.
LASERS = [(0, 8), (1500, 14), (6000, 22), (20000, 34), (60000, 50), (150000, 70)]
# (price, absorption)
SHIELDS = [(0, 0), (1200, 4), (5000, 9), (18000, 15), (55000, 22), (140000, 30)]
# (price, cargo capacity)
HOLDS = [(0, 30), (2000, 60), (8000, 100), (25000, 160), (80000, 250)]

BOSS_HP = 700
BOSS_DMG = 42


# -- Ship -------------------------------------------------------------------

def _fresh():
    return {
        "credits": 300, "bank": 0, "sector": 1, "fuel": WARPS_PER_DAY,
        "laser": 0, "shield": 0, "hold": 0, "hull": 50, "kits": 1,
        "cargo": {g: 0 for g in GOODS},
        "day": "", "alive": True,
        "kills": 0, "deaths": 0, "duels": 0, "runs": 0,
    }


def max_hull(ship):
    return 50 + ship["shield"] * 20


def laser_power(ship):
    return LASERS[ship["laser"]][1]


def absorption(ship):
    return SHIELDS[ship["shield"]][1]


def hold_size(ship):
    return HOLDS[ship["hold"]][1]


def cargo_load(ship):
    return sum(ship["cargo"].values())


def net_worth(ship):
    goods = sum(ship["cargo"][g] * BASE_PRICE[g] for g in GOODS)
    return ship["credits"] + ship["bank"] + goods


def load_ship():
    """Load the ship and, if a day has passed since the last docking,
    open a new game day: the tanks are full, the wrecked fly again."""
    ship = {**_fresh(), **(load_section(SECTION) or {})}
    ship["cargo"] = {g: int(ship["cargo"].get(g, 0)) for g in GOODS}
    today = date.today().isoformat()
    if ship.get("day") != today:
        ship["day"] = today
        ship["fuel"] = WARPS_PER_DAY
        ship["alive"] = True
        ship["hull"] = max_hull(ship)
    ship["hull"] = min(ship["hull"], max_hull(ship))
    return ship


def save_ship(ship):
    save_section(SECTION, ship)
    _record(ship)


def _record(ship):
    """The arcade shows one number per game — here the best net worth."""
    games = load_section("games")
    if net_worth(ship) > int(games.get("space", 0)):
        games["space"] = net_worth(ship)
        save_section("games", games)


# -- The market -------------------------------------------------------------

def price(good, sector, day):
    """Today's price for a good in a sector. Deterministic within a day,
    so a route stays worth flying until midnight: each sector has a fixed
    taste for each good, the day adds a little static on top."""
    gi = GOODS.index(good)
    flavour = 0.6 + ((sector * 5 + gi * 7) % 9) / 10.0
    static = random.Random(f"{day}:{sector}:{good}").uniform(0.88, 1.12)
    return max(2, int(BASE_PRICE[good] * flavour * static))


def sector_name(sector):
    return t("space.sector_names").split("|")[sector - 1]


# -- Pirates ----------------------------------------------------------------

def _power(ship):
    """Rough measure of how dangerous the ship already is — the lanes
    answer in kind."""
    return ship["laser"] + ship["shield"]


def pirate_for(ship):
    prefixes = t("space.pirate_prefixes").split("|")
    hulls = t("space.pirate_hulls").split("|")
    p = _power(ship)
    return {
        "name": f"{random.choice(prefixes)} {random.choice(hulls)}",
        "hp": 30 + p * 22 + random.randint(0, 20),
        "dmg": 6 + p * 5,
        "credits": 60 + p * 90 + random.randint(0, 40 + p * 40),
    }


def _caller_pirate(ship):
    """Another caller as a pirate captain — the personas from users.py.
    Without a pool (no AI key, nobody ever online) the lanes stay anonymous."""
    pool = (load_section("users") or {}).get("pool") or []
    handles = [str(p.get("handle", "")).strip() for p in pool if isinstance(p, dict)]
    handles = [h for h in handles if h]
    if not handles:
        return None
    handle = random.choice(handles)
    # Derive stats from the handle: the same captain is always equally strong.
    seed = sum(ord(c) for c in handle)
    p = _power(ship)
    return {
        "name": handle,
        "hp": 40 + p * 24 + seed % 30,
        "dmg": 7 + p * 5 + seed % 4,
        "credits": 100 + p * 110 + seed % 80,
        "caller": True,
    }


# -- Combat -----------------------------------------------------------------

def _bar(term, ship, foe):
    term.type_out(
        t("space.combat_status", you=ship["hull"], max=max_hull(ship),
          foe=foe["name"], foe_hp=max(foe["hp"], 0)), delay=0)


def fight(term, ship, foe, can_flee=True):
    """A fight until it's decided. Returns 'win', 'flee', or 'dead'."""
    term.rule(t("space.combat_title", foe=foe["name"]))
    term.type_out(t("space.combat_intro", foe=foe["name"]), delay=0.004)
    while True:
        _bar(term, ship, foe)
        choice = (term.prompt(t("space.combat_prompt")) or "").strip().lower()[:1]
        if choice == "w" and can_flee:
            if random.random() < 0.55:
                term.type_out(t("space.flee_ok"), delay=0.004)
                return "flee"
            term.type_out(t("space.flee_fail"), delay=0.004)
        elif choice == "w":
            term.type_out(t("space.flee_blocked"), delay=0.004)
            continue
        elif choice == "n":
            if ship["kits"] <= 0:
                term.type_out(t("space.no_kit"), delay=0.003)
                continue
            ship["kits"] -= 1
            fixed = min(KIT_REPAIR, max_hull(ship) - ship["hull"])
            ship["hull"] += fixed
            term.type_out(t("space.kit_used", hull=fixed, left=ship["kits"]), delay=0.004)
        elif choice == "s":
            show_log(term, ship)
            continue
        else:
            # Everything else fires the lasers — when in doubt, shoot.
            dmg = random.randint(laser_power(ship) // 2, laser_power(ship)) + 1
            crit = random.random() < 0.12
            if crit:
                dmg *= 2
            foe["hp"] -= dmg
            term.type_out(
                t("space.hit_crit" if crit else "space.hit", foe=foe["name"], dmg=dmg),
                delay=0.004)
            if foe["hp"] <= 0:
                term.type_out(t("space.foe_down", foe=foe["name"]), delay=0.005)
                term.beep()
                return "win"

        back = max(1, random.randint(foe["dmg"] // 2, foe["dmg"]) - absorption(ship) // 2)
        ship["hull"] -= back
        term.type_out(t("space.foe_hit", foe=foe["name"], dmg=back), delay=0.004)
        if ship["hull"] <= 0:
            ship["hull"] = 0
            return "dead"


def _wrecked(term, ship, foe):
    """The escape pod saves the pilot, not the freight: cargo and cash on
    hand stay with the wreck, the bank account survives."""
    ship["alive"] = False
    ship["deaths"] += 1
    lost, ship["credits"] = ship["credits"], 0
    ship["cargo"] = {g: 0 for g in GOODS}
    ship["fuel"] = 0
    save_ship(ship)
    term.rule(t("space.wreck_title"))
    term.type_out(t("space.wreck_msg", foe=foe["name"], credits=lost), delay=0.005)
    term.type_out(t("space.wreck_hint"), delay=0.003)
    term.beep(2)
    term.pause()


def _won(term, ship, foe):
    ship["credits"] += foe["credits"]
    ship["kills"] += 1
    if foe.get("caller"):
        ship["duels"] += 1
    term.type_out(t("space.spoils", credits=foe["credits"]), delay=0.004)
    save_ship(ship)
    term.pause()


# -- The lanes --------------------------------------------------------------

def _distance(a, b):
    """The sectors sit on a ring — fuel burns per hop, whichever way round."""
    d = abs(a - b)
    return min(d, SECTORS - d)


def warp(term, ship):
    if not ship["alive"]:
        term.error(t("space.you_are_wrecked"))
        term.pause()
        return
    raw = (term.prompt(t("space.warp_prompt", sectors=SECTORS)) or "").strip()
    if not raw.isdigit():
        return
    target = int(raw)
    if not 1 <= target <= SECTORS or target == ship["sector"]:
        return
    cost = _distance(ship["sector"], target)
    if ship["fuel"] < cost:
        term.error(t("space.no_fuel", need=cost, have=ship["fuel"]))
        term.pause()
        return
    ship["fuel"] -= cost
    ship["sector"] = target
    term.type_out(t("space.warp_done", sector=sector_name(target), fuel=cost), delay=0.005)
    # The longer the jump, the longer the lanes have you on their screens.
    if random.random() < 0.16 + cost * 0.05:
        foe = _caller_pirate(ship) if random.random() < 0.25 else None
        if foe:
            term.type_out(t("space.caller_ambush", handle=foe["name"]), delay=0.005)
        else:
            foe = pirate_for(ship)
        outcome = fight(term, ship, foe)
        if outcome == "win":
            _won(term, ship, foe)
            return
        if outcome == "dead":
            _wrecked(term, ship, foe)
            return
    save_ship(ship)


# -- The trade post ---------------------------------------------------------

def trade(term, ship):
    def rows():
        out = [(None, t("space.trade_head", sector=sector_name(ship["sector"])), "")]
        for i, good in enumerate(GOODS, 1):
            out.append((str(i), t(f"space.good_{good}"),
                        t("space.trade_row", price=price(good, ship["sector"], ship["day"]),
                          have=ship["cargo"][good])))
        return out

    while True:
        choice = lightbar.menu(
            term, t("space.trade_title"), rows,
            subtitle=t("space.trade_subtitle", credits=ship["credits"],
                       load=cargo_load(ship), hold=hold_size(ship)))
        if not choice or not choice.isdigit():
            return
        idx = int(choice) - 1
        if not 0 <= idx < len(GOODS):
            continue
        good = GOODS[idx]
        rate = price(good, ship["sector"], ship["day"])
        raw = (term.prompt(t("space.trade_amount")) or "").strip()
        sell = raw.startswith("-")
        raw = raw.lstrip("+-")
        if not raw.isdigit():
            continue
        amount = int(raw)
        if sell:
            amount = min(amount, ship["cargo"][good])
            if amount <= 0:
                continue
            ship["cargo"][good] -= amount
            ship["credits"] += amount * rate
            term.type_out(t("space.trade_sold", n=amount, good=t(f"space.good_{good}"),
                            credits=amount * rate), delay=0.004)
        else:
            room = hold_size(ship) - cargo_load(ship)
            amount = min(amount, room, ship["credits"] // rate)
            if amount <= 0:
                term.type_out(t("space.trade_no_room" if room <= 0 else "space.too_poor",
                                missing=rate - ship["credits"]), delay=0.004)
                continue
            ship["cargo"][good] += amount
            ship["credits"] -= amount * rate
            term.type_out(t("space.trade_bought", n=amount, good=t(f"space.good_{good}"),
                            credits=amount * rate), delay=0.004)
        save_ship(ship)


# -- The dock ---------------------------------------------------------------

def _outfitter(term, ship, kind):
    """Laser and shield dock — same counter, two racks."""
    table = LASERS if kind == "laser" else SHIELDS
    slot = "laser" if kind == "laser" else "shield"

    def rows():
        out = []
        for i, (cost, power) in enumerate(table):
            name = t(f"space.{kind}_{i}")
            if i == ship[slot]:
                value = t("space.dock_fitted")
            elif i < ship[slot]:
                value = t("space.dock_scrapped")
            else:
                value = t("space.dock_price", price=cost, power=power)
            out.append((str(i + 1), name, value))
        return out

    while True:
        choice = lightbar.menu(
            term, t(f"space.dock_title_{kind}"), rows,
            subtitle=t("space.dock_subtitle", credits=ship["credits"]))
        if not choice or not choice.isdigit():
            return
        idx = int(choice) - 1
        if not 0 <= idx < len(table):
            continue
        cost = table[idx][0]
        if idx <= ship[slot]:
            term.type_out(t("space.dock_have_better"), delay=0.003)
            continue
        if ship["credits"] < cost:
            term.type_out(t("space.too_poor", missing=cost - ship["credits"]), delay=0.004)
            continue
        ship["credits"] -= cost
        ship[slot] = idx
        if slot == "shield":
            ship["hull"] = min(ship["hull"], max_hull(ship))
        save_ship(ship)
        term.type_out(t("space.dock_bought", name=t(f"space.{kind}_{idx}")), delay=0.004)


def station(term, ship):
    """Station office: repairs, nanokits, the cargo hold and the account."""
    def rows():
        missing = max_hull(ship) - ship["hull"]
        upgrade = t("space.station_hold_max") if ship["hold"] + 1 >= len(HOLDS) else \
            t("space.station_hold_value", price=HOLDS[ship["hold"] + 1][0],
              size=HOLDS[ship["hold"] + 1][1])
        return [
            ("1", t("space.station_repair"), t("space.station_repair_value",
                                               hull=missing, price=missing * 3)),
            ("2", t("space.station_kit"), t("space.station_kit_value",
                                            price=KIT_PRICE, have=ship["kits"])),
            ("3", t("space.station_hold"), upgrade),
            ("4", t("space.station_deposit"), t("space.station_bank_value", bank=ship["bank"])),
            ("5", t("space.station_withdraw"), t("space.station_bank_value", bank=ship["bank"])),
        ]

    while True:
        choice = lightbar.menu(term, t("space.station_title"), rows,
                               subtitle=t("space.dock_subtitle", credits=ship["credits"]))
        if not choice:
            return
        if choice == "1":
            missing = max_hull(ship) - ship["hull"]
            if missing <= 0:
                term.type_out(t("space.station_intact"), delay=0.003)
                continue
            cost = missing * 3
            if ship["credits"] < cost:
                # Patch as much plating as the credits allow.
                missing = ship["credits"] // 3
                cost = missing * 3
            if missing <= 0:
                term.type_out(t("space.too_poor", missing=3 - ship["credits"]), delay=0.004)
                continue
            ship["credits"] -= cost
            ship["hull"] += missing
            save_ship(ship)
            term.type_out(t("space.station_repaired", hull=missing, price=cost), delay=0.004)
        elif choice == "2":
            if ship["credits"] < KIT_PRICE:
                term.type_out(t("space.too_poor", missing=KIT_PRICE - ship["credits"]), delay=0.004)
                continue
            ship["credits"] -= KIT_PRICE
            ship["kits"] += 1
            save_ship(ship)
            term.type_out(t("space.station_kit_bought", have=ship["kits"]), delay=0.004)
        elif choice == "3":
            if ship["hold"] + 1 >= len(HOLDS):
                term.type_out(t("space.station_hold_max"), delay=0.003)
                continue
            cost = HOLDS[ship["hold"] + 1][0]
            if ship["credits"] < cost:
                term.type_out(t("space.too_poor", missing=cost - ship["credits"]), delay=0.004)
                continue
            ship["credits"] -= cost
            ship["hold"] += 1
            save_ship(ship)
            term.type_out(t("space.station_hold_bought", size=hold_size(ship)), delay=0.004)
        elif choice in ("4", "5"):
            amount = (term.prompt(t("space.station_amount")) or "").strip()
            if not amount.isdigit():
                continue
            amount = int(amount)
            if choice == "4":
                amount = min(amount, ship["credits"])
                ship["credits"] -= amount
                ship["bank"] += amount
            else:
                amount = min(amount, ship["bank"])
                ship["bank"] -= amount
                ship["credits"] += amount
            save_ship(ship)
            term.type_out(t("space.station_bank_ok", credits=ship["credits"],
                            bank=ship["bank"]), delay=0.004)


# -- The colossus -----------------------------------------------------------

def colossus(term, ship):
    """The final battle in the wreck field. Whoever wins starts over,
    with the run counted."""
    if ship["sector"] != BOSS_SECTOR:
        term.type_out(t("space.boss_elsewhere", sector=sector_name(BOSS_SECTOR)), delay=0.004)
        term.pause()
        return
    if ship["laser"] < BOSS_MIN_LASER:
        term.type_out(t("space.boss_too_weak", laser=t(f"space.laser_{BOSS_MIN_LASER}")),
                      delay=0.004)
        term.pause()
        return
    if not ship["alive"]:
        term.error(t("space.you_are_wrecked"))
        term.pause()
        return
    term.rule(t("space.boss_title"))
    term.type_out(t("space.boss_intro"), delay=0.006)
    foe = {"name": t("space.boss_name"), "hp": BOSS_HP, "dmg": BOSS_DMG, "credits": 0}
    if fight(term, ship, foe, can_flee=False) == "dead":
        _wrecked(term, ship, foe)
        return
    ship["runs"] += 1
    term.rule(t("space.boss_won_title"))
    term.type_out(t("space.boss_won", times=ship["runs"]), delay=0.006)
    term.beep(3)
    # New run: the freighter is gone, the legend stays.
    keep = {k: ship[k] for k in ("kills", "deaths", "duels", "runs", "day")}
    ship.update(_fresh())
    ship.update(keep)
    ship["hull"] = max_hull(ship)
    save_ship(ship)
    term.pause()


def show_log(term, ship):
    handle = (load_section("profile") or {}).get("handle", "GAST")
    term.rule(t("space.log_title", handle=handle))
    hold = ", ".join(f"{t(f'space.good_{g}')}: {ship['cargo'][g]}" for g in GOODS)
    term.box([
        f"{label:<22}{value}" for label, value in (
            (t("space.stat_sector"), sector_name(ship["sector"])),
            (t("space.stat_hull"), f"{ship['hull']} / {max_hull(ship)}"),
            (t("space.stat_laser"), t(f"space.laser_{ship['laser']}")),
            (t("space.stat_shield"), t(f"space.shield_{ship['shield']}")),
            (t("space.stat_hold"), f"{cargo_load(ship)} / {hold_size(ship)}  ({hold})"),
            (t("space.stat_credits"), f"{ship['credits']}  ({t('space.stat_bank')}: {ship['bank']})"),
            (t("space.stat_kits"), str(ship["kits"])),
            (t("space.stat_fuel"), str(ship["fuel"])),
            (t("space.stat_kills"), f"{ship['kills']}  ({t('space.stat_duels')}: {ship['duels']})"),
            (t("space.stat_runs"), str(ship["runs"])),
            (t("space.stat_worth"), str(net_worth(ship))),
        )])
    term.pause()


# -- The bridge -------------------------------------------------------------

def run(term):
    """Entry point from the arcade: the bridge with all stations."""
    ship = load_ship()
    save_ship(ship)
    term.rule(t("space.title"))
    term.type_out(t("space.welcome"), delay=0.005)

    def rows():
        state = t("space.state_wrecked") if not ship["alive"] else \
            t("space.state_flying", hull=ship["hull"], max=max_hull(ship))
        return [
            (None, t("space.head_lanes"), ""),
            ("1", t("space.menu_warp"), t("space.menu_warp_value", fuel=ship["fuel"])),
            ("2", t("space.menu_trade"), t("space.menu_trade_value",
                                           load=cargo_load(ship), hold=hold_size(ship))),
            ("3", t("space.menu_boss"), t("space.menu_boss_value")),
            (None, t("space.head_dock"), ""),
            ("4", t("space.menu_lasers"), t(f"space.laser_{ship['laser']}")),
            ("5", t("space.menu_shields"), t(f"space.shield_{ship['shield']}")),
            ("6", t("space.menu_station"), t("space.menu_station_value", credits=ship["credits"])),
            ("7", t("space.menu_log"), state),
        ]

    at = "1"
    while True:
        choice = lightbar.menu(term, t("space.title"), rows,
                               subtitle=t("space.menu_subtitle",
                                          sector=sector_name(ship["sector"]),
                                          credits=ship["credits"]),
                               start=at)
        if not choice or choice in ("q", "0"):
            save_ship(ship)
            return
        at = choice
        if choice == "1":
            warp(term, ship)
        elif choice == "2":
            trade(term, ship)
        elif choice == "3":
            colossus(term, ship)
        elif choice == "4":
            _outfitter(term, ship, "laser")
        elif choice == "5":
            _outfitter(term, ship, "shield")
        elif choice == "6":
            station(term, ship)
        elif choice == "7":
            show_log(term, ship)
        else:
            term.error(t("space.unknown_choice"))
