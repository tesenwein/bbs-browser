"""Weather and clocks: the board's own weather station.

Every real board had a bulletin with the local forecast, and the SysOp's
desk had a row of clocks for the other continents. Both live here.

The data comes from Open-Meteo — no key, no account, no tracking — and is
cached in the database for half an hour, so paging back and forth doesn't
hammer the service. Without a configured location the module stays quiet:
no network call, no error, just an empty panel.
"""

import threading
import time
from datetime import datetime

import requests

from . import db
from .constants import USER_AGENT
from .i18n import t

SECTION = "weather"
CACHE_SECTION = "weather_cache"

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

TTL_MINUTES = 30       # a forecast doesn't change faster than that
FORECAST_DAYS = 4      # today plus three
MAX_CLOCKS = 6
TIMEOUT = 12


# -- Configuration ---------------------------------------------------------


def config():
    cfg = db.get_section(SECTION)
    return {
        "place": cfg.get("place", ""),
        "lat": cfg.get("lat"),
        "lon": cfg.get("lon"),
        "tz": cfg.get("tz", "auto"),
        "units": cfg.get("units", "metric"),
        "clocks": cfg.get("clocks", []),
    }


def save_config(cfg):
    db.set_section(SECTION, cfg)


def configured():
    cfg = config()
    return cfg["lat"] is not None and cfg["lon"] is not None


def set_place(place, lat, lon, tz="auto"):
    cfg = config()
    cfg.update({"place": place, "lat": lat, "lon": lon, "tz": tz or "auto"})
    save_config(cfg)
    clear()


def clear_place():
    cfg = config()
    cfg.update({"place": "", "lat": None, "lon": None, "tz": "auto"})
    save_config(cfg)
    clear()


# -- Cache -----------------------------------------------------------------


def _cache_key(cfg):
    return f"{cfg['lat']:.3f},{cfg['lon']:.3f},{cfg['units']}"


def cache():
    """The stored forecast — {} when it belongs to another place."""
    data = db.get_section(CACHE_SECTION)
    if not data.get("data") or not configured():
        return {}
    if data.get("key") != _cache_key(config()):
        return {}
    return data


def age_minutes():
    ts = cache().get("ts", 0)
    return (time.time() - ts) / 60 if ts else None


def stale():
    age = age_minutes()
    return age is None or age >= TTL_MINUTES


def clear():
    db.set_section(CACHE_SECTION, {})


# -- Source ----------------------------------------------------------------


def geocode(name, limit=6):
    """Place search: [(label, lat, lon, timezone)] — [] on any trouble."""
    from .i18n import get_lang
    try:
        resp = requests.get(GEO_URL, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT},
                            params={"name": name, "count": limit,
                                    "language": get_lang(), "format": "json"})
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception:
        return []
    out = []
    for entry in results:
        parts = [entry.get("name", "")]
        if entry.get("admin1"):
            parts.append(entry["admin1"])
        if entry.get("country"):
            parts.append(entry["country"])
        out.append((", ".join(p for p in parts if p),
                    entry.get("latitude"), entry.get("longitude"),
                    entry.get("timezone") or "auto"))
    return [row for row in out if row[1] is not None and row[2] is not None]


def _params(cfg):
    imperial = cfg["units"] == "imperial"
    return {
        "latitude": cfg["lat"],
        "longitude": cfg["lon"],
        "timezone": cfg["tz"] or "auto",
        "forecast_days": FORECAST_DAYS,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "wind_speed_10m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset",
        "temperature_unit": "fahrenheit" if imperial else "celsius",
        "wind_speed_unit": "mph" if imperial else "kmh",
    }


def refresh(force=False):
    """Fetches the forecast when the cache has expired. Returns the data
    dict (possibly {}); never raises, never prints."""
    if not configured():
        return {}
    if not force and not stale():
        return cache().get("data", {})
    cfg = config()
    try:
        resp = requests.get(FORECAST_URL, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT}, params=_params(cfg))
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # A failed call must not throw away a forecast that is merely old —
        # a slightly stale panel beats an empty one.
        return cache().get("data", {})
    if not data.get("current"):
        return cache().get("data", {})
    db.set_section(CACHE_SECTION, {"key": _cache_key(cfg), "ts": time.time(), "data": data})
    return data


def data():
    """The cached forecast without touching the network."""
    return cache().get("data", {})


_thread = None


def refresh_async():
    """Starts the fetch next to the dial-in sequence, so the welcome box
    already knows the weather by the time it is drawn."""
    global _thread
    if not configured() or not stale():
        return None
    if _thread and _thread.is_alive():
        return _thread
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    return _thread


def _run():
    try:
        refresh()
    except Exception:
        pass


def wait(seconds=1.5):
    """Gives a running fetch a moment before the welcome box is printed."""
    if _thread and _thread.is_alive():
        _thread.join(seconds)


# -- Weather codes ---------------------------------------------------------


def _group(code):
    """WMO weather code -> one of our art/label groups."""
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "overcast"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if 95 <= code <= 99:
        return "thunder"
    if 80 <= code <= 82:
        return "showers"
    return "rain"


# Five lines of CP437 art per group — the sky over the message base.
ART = {
    "clear": ["   \\   /   ",
              "    .-.    ",
              " --(   )-- ",
              "    `-'    ",
              "   /   \\   "],
    "partly": ["   \\  /    ",
               " _ /\"\".-.  ",
               "   \\_(   ) ",
               "   /(___(__",
               "           "],
    "overcast": ["           ",
                 "     .--.  ",
                 "  .-(    ). ",
                 " (___.__)__)",
                 "           "],
    "fog": ["           ",
            " _ - _ - _ ",
            "  _ - _ -  ",
            " _ - _ - _ ",
            "           "],
    "drizzle": ["     .-.   ",
                "    (   ). ",
                "   (___(__)",
                "    ' ' '  ",
                "   ' ' '   "],
    "rain": ["     .-.   ",
             "    (   ). ",
             "   (___(__)",
             "   ,',',', ",
             "   ,',',', "],
    "showers": ["   _`/\"\".-.",
                "    ,\\_(   )",
                "     /(___(__)",
                "     ',',','",
                "     ' ' ' "],
    "snow": ["     .-.   ",
             "    (   ). ",
             "   (___(__)",
             "    *  *  *",
             "   *  *  * "],
    "thunder": ["     .-.   ",
                "    (   ). ",
                "   (___(__)",
                "    /_  /_ ",
                "     /   / "],
}

ICON = {
    "clear": "*", "partly": "%", "overcast": "=", "fog": "~",
    "drizzle": "'", "rain": ",", "showers": ";", "snow": "x", "thunder": "!",
}


def describe(code):
    return t("weather.code_" + _group(code))


# -- Formatting helpers ----------------------------------------------------


def _hhmm(iso):
    """'2026-07-22T06:12' -> '06:12'. Anything unexpected stays empty."""
    if not iso or "T" not in iso:
        return ""
    return iso.split("T", 1)[1][:5]


def _weekday(iso):
    from .nostalgia import _get_weekdays
    try:
        day = datetime.strptime(iso[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
    return _get_weekdays()[day.weekday()][:2]


def _units(payload, block, field):
    return (payload.get(block + "_units") or {}).get(field, "")


def sun_times():
    """('06:12', '20:45') for today — ('', '') without data."""
    daily = data().get("daily") or {}
    rise = (daily.get("sunrise") or [""])[0]
    down = (daily.get("sunset") or [""])[0]
    return _hhmm(rise), _hhmm(down)


def panel_line():
    """One line for the welcome box — "" when nothing is known yet."""
    payload = data()
    current = payload.get("current") or {}
    if not current:
        return ""
    temp = current.get("temperature_2m")
    if temp is None:
        return ""
    unit = _units(payload, "current", "temperature_2m") or "°"
    rise, down = sun_times()
    # The panel row is narrow — the canton and country of the stored label
    # would push the sun times off the box, so only the town name is shown.
    place = (config()["place"] or t("weather.unknown_place")).split(",")[0]
    line = t("weather.panel", icon=ICON[_group(current.get("weather_code", 0))],
             temp=round(temp), unit=unit,
             text=describe(current.get("weather_code", 0)), place=place)
    if rise and down:
        line += "  " + t("weather.panel_sun", rise=rise, sunset=down)
    return line


# -- Clocks ----------------------------------------------------------------


def clock_rows():
    """[(label, 'HH:MM', 'day/night marker')] for the configured zones."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:      # pragma: no cover - Python < 3.9
        return []
    rows = []
    for zone in config()["clocks"][:MAX_CLOCKS]:
        try:
            now = datetime.now(ZoneInfo(zone))
        except Exception:
            # A zone the system has no tzdata for is skipped, not fatal.
            continue
        label = zone.rsplit("/", 1)[-1].replace("_", " ")
        marker = t("weather.clock_day") if 6 <= now.hour < 20 else t("weather.clock_night")
        rows.append((label, now.strftime("%H:%M"), f"{now.strftime('%d.%m.')} {marker}"))
    return rows


def add_clock(zone):
    """Adds a time zone; returns False when it is unknown or already there."""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(zone)
    except Exception:
        return False
    cfg = config()
    zones = list(cfg["clocks"])
    if zone in zones or len(zones) >= MAX_CLOCKS:
        return False
    zones.append(zone)
    cfg["clocks"] = zones
    save_config(cfg)
    return True


def remove_clock(zone):
    cfg = config()
    zones = [z for z in cfg["clocks"] if z != zone]
    if len(zones) == len(cfg["clocks"]):
        return False
    cfg["clocks"] = zones
    save_config(cfg)
    return True


# -- Presentation ----------------------------------------------------------


def page():
    """The weather station as a page: today's sky in ASCII next to the
    readings, three more days below, then the SysOp's row of clocks."""
    from .page import Page

    pg = Page("bbs://weather", t("weather.page_title"))
    if not configured():
        pg.blocks.append({"type": "heading", "content": t("weather.page_title")})
        pg.blocks.append({"type": "text", "content": t("weather.no_place")})
        _append_clocks(pg)
        return pg

    payload = data()
    current = payload.get("current") or {}
    place = config()["place"] or t("weather.unknown_place")
    pg.blocks.append({"type": "heading", "content": t("weather.page_heading", place=place)})
    if not current:
        pg.blocks.append({"type": "text", "content": t("weather.no_data")})
        _append_clocks(pg)
        return pg

    code = current.get("weather_code", 0)
    t_unit = _units(payload, "current", "temperature_2m")
    w_unit = _units(payload, "current", "wind_speed_10m")
    rise, down = sun_times()
    facts = [
        describe(code),
        t("weather.fact_temp", temp=round(current.get("temperature_2m", 0)), unit=t_unit),
        t("weather.fact_feels", temp=round(current.get("apparent_temperature", 0)), unit=t_unit),
        t("weather.fact_wind", wind=round(current.get("wind_speed_10m", 0)), unit=w_unit),
        t("weather.fact_humidity", humidity=current.get("relative_humidity_2m", 0)),
    ]
    art = ART[_group(code)]
    lines = []
    for i in range(max(len(art), len(facts))):
        left = art[i] if i < len(art) else " " * 11
        right = facts[i] if i < len(facts) else ""
        lines.append(f"  {left:<13}{right}")
    if rise and down:
        lines.append("")
        lines.append("  " + t("weather.sun_line", rise=rise, sunset=down))
    pg.blocks.append({"type": "pre", "content": "\n".join(lines)})

    _append_forecast(pg, payload)
    _append_clocks(pg)
    age = age_minutes()
    pg.blocks.append({"type": "text", "content": t(
        "weather.page_age", minutes=int(age or 0), source="Open-Meteo")})
    return pg


def _append_forecast(pg, payload):
    daily = payload.get("daily") or {}
    days = daily.get("time") or []
    if len(days) < 2:
        return
    unit = _units(payload, "daily", "temperature_2m_max")
    rows = []
    for i, day in enumerate(days[:FORECAST_DAYS]):
        label = t("weather.today") if i == 0 else f"{_weekday(day)} {day[8:10]}.{day[5:7]}."
        code = (daily.get("weather_code") or [0] * len(days))[i]
        high = (daily.get("temperature_2m_max") or [0] * len(days))[i]
        low = (daily.get("temperature_2m_min") or [0] * len(days))[i]
        rain = (daily.get("precipitation_probability_max") or [None] * len(days))[i]
        rain_txt = f"{rain:>3d}%" if isinstance(rain, int) else "   -"
        rows.append(f"  {label:<10} {ICON[_group(code)]} {describe(code):<22}"
                    f"{round(low):>3}/{round(high):<3}{unit}  {rain_txt}")
    pg.blocks.append({"type": "heading", "content": t("weather.forecast_heading")})
    pg.blocks.append({"type": "pre", "content": "\n".join(rows)})


def _append_clocks(pg):
    rows = clock_rows()
    if not rows:
        return
    pg.blocks.append({"type": "heading", "content": t("weather.clocks_heading")})
    pg.blocks.append({"type": "pre", "content": "\n".join(
        f"  {label:<18} {clock}  {note}" for label, clock, note in rows)})
