"""Weather station submenu: place, units and world clocks.

Named like the top-level ``bbs_browser.weather`` module on purpose — the
data module is always imported as ``from .. import weather`` here.
"""

from .. import lightbar
from ..i18n import t
from ..menukit import cycle as _cycle


def _weather_summary():
    """Short status of the weather station for the main menu row."""
    from .. import weather
    cfg = weather.config()
    clocks = len(cfg["clocks"])
    if not weather.configured():
        return t("configmenu.weather_no_place", clocks=clocks)
    line = weather.panel_line()
    return line or t("configmenu.weather_pending", place=cfg["place"])


def _weather_menu(term):
    """Location, units and world clocks of the weather station — the one
    place where the caller sets up what greets him in the welcome box."""
    from .. import weather

    def rows():
        cfg = weather.config()
        clocks = ", ".join(z.rsplit("/", 1)[-1].replace("_", " ")
                           for z in cfg["clocks"]) or t("configmenu.not_set")
        return [
            ("1", t("configmenu.weather_place"), cfg["place"] or t("configmenu.not_set")),
            ("2", t("configmenu.weather_units"), t("configmenu.weather_units_" + cfg["units"])),
            ("3", t("configmenu.weather_clocks"), clocks),
            ("4", t("configmenu.weather_clock_remove"), ""),
            ("5", t("configmenu.weather_refresh"), _weather_summary()),
        ]

    def cycle(key, direction):
        if key != "2":
            return False
        cfg = weather.config()
        cfg["units"] = _cycle(("metric", "imperial"), cfg["units"], direction or 1)
        weather.save_config(cfg)
        weather.clear()
        return True

    at = "1"
    while True:
        choice = lightbar.menu(term, t("configmenu.title_weather"), rows,
                               on_cycle=cycle, start=at)
        if not choice:
            return
        at = choice
        if cycle(choice, 1):
            continue
        if choice == "1":
            _weather_place_prompt(term)
        elif choice == "3":
            zone = term.prompt(t("configmenu.prompt_weather_clock")).strip()
            if not zone:
                continue
            if weather.add_clock(zone):
                term.type_out(t("weather.clock_added", zone=zone), delay=0.003)
            else:
                term.error(t("weather.clock_invalid"))
        elif choice == "4":
            zones = weather.config()["clocks"]
            if not zones:
                continue
            picked = lightbar.menu(term, t("configmenu.title_weather_clocks"),
                                   [(z, z, "") for z in zones])
            if picked and weather.remove_clock(picked):
                term.type_out(t("weather.clock_removed", zone=picked), delay=0.003)
        elif choice == "5":
            if not weather.configured():
                term.error(t("weather.no_place"))
            else:
                term.type_out(t("weather.fetching"), delay=0.003)
                if weather.refresh(force=True):
                    term.type_out(weather.panel_line(), delay=0.003)
                else:
                    term.error(t("weather.refresh_failed"))


def _weather_place_prompt(term):
    """Place search: type a name, pick from the hits — '-' clears the place."""
    from .. import weather
    query = term.prompt(t("configmenu.prompt_weather_place")).strip()
    if not query:
        return
    if query == "-":
        weather.clear_place()
        term.type_out(t("weather.place_cleared"), delay=0.003)
        return
    term.type_out(t("weather.searching"), delay=0.003)
    hits = weather.geocode(query)
    if not hits:
        term.error(t("weather.search_empty"))
        return
    rows = [(str(i), label, "") for i, (label, _, _, _) in enumerate(hits, 1)]
    choice = lightbar.menu(term, t("configmenu.title_weather_place"), rows)
    if not choice:
        return
    label, lat, lon, tz = hits[int(choice) - 1]
    weather.set_place(label, lat, lon, tz)
    term.type_out(t("weather.place_saved", place=label), delay=0.003)
    weather.refresh(force=True)
