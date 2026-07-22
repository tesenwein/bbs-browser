"""Texte des Wetter- und Uhrenmoduls (weather.py)."""

STRINGS = {
    # -- Wettercodes
    "weather.code_clear": {"de": "Klar", "en": "Clear"},
    "weather.code_partly": {"de": "Teils bewoelkt", "en": "Partly cloudy"},
    "weather.code_overcast": {"de": "Bedeckt", "en": "Overcast"},
    "weather.code_fog": {"de": "Nebel", "en": "Fog"},
    "weather.code_drizzle": {"de": "Nieselregen", "en": "Drizzle"},
    "weather.code_rain": {"de": "Regen", "en": "Rain"},
    "weather.code_showers": {"de": "Schauer", "en": "Showers"},
    "weather.code_snow": {"de": "Schnee", "en": "Snow"},
    "weather.code_thunder": {"de": "Gewitter", "en": "Thunderstorm"},

    # -- Panel und Seite
    "weather.panel": {"de": "{icon} {temp}{unit}  {text} — {place}",
                      "en": "{icon} {temp}{unit}  {text} — {place}"},
    "weather.panel_sun": {"de": "auf {rise} / unter {sunset}",
                          "en": "up {rise} / down {sunset}"},
    "weather.unknown_place": {"de": "Unbekannter Ort", "en": "Unknown place"},
    "weather.page_title": {"de": "WETTERSTATION", "en": "WEATHER STATION"},
    "weather.page_heading": {"de": "Wetterstation — {place}", "en": "Weather station — {place}"},
    "weather.page_age": {"de": "Messwerte vor {minutes} min abgerufen — Quelle: {source}",
                         "en": "Readings fetched {minutes} min ago — source: {source}"},
    "weather.no_place": {"de": "Kein Ort gesetzt. Unter 'c' > Wetter & Uhr einen Ort suchen.",
                         "en": "No location set. Search one under 'c' > Weather & clock."},
    "weather.no_data": {"de": "Noch keine Messwerte — 'we r' frischt auf.",
                        "en": "No readings yet — 'we r' refreshes."},
    "weather.fact_temp": {"de": "Temperatur   {temp}{unit}", "en": "Temperature  {temp}{unit}"},
    "weather.fact_feels": {"de": "Gefuehlt     {temp}{unit}", "en": "Feels like   {temp}{unit}"},
    "weather.fact_wind": {"de": "Wind         {wind} {unit}", "en": "Wind         {wind} {unit}"},
    "weather.fact_humidity": {"de": "Feuchte      {humidity}%", "en": "Humidity     {humidity}%"},
    "weather.sun_line": {"de": "Sonnenaufgang {rise}   Sonnenuntergang {sunset}",
                         "en": "Sunrise {rise}   Sunset {sunset}"},
    "weather.forecast_heading": {"de": "Vorschau", "en": "Forecast"},
    "weather.today": {"de": "Heute", "en": "Today"},
    "weather.clocks_heading": {"de": "Weltzeit", "en": "World clocks"},
    "weather.clock_day": {"de": "Tag", "en": "day"},
    "weather.clock_night": {"de": "Nacht", "en": "night"},

    # -- Browser-Kommando
    "weather.fetching": {"de": "Wetterstation wird abgefragt ...", "en": "Querying the weather station ..."},
    "weather.refresh_failed": {"de": "Die Wetterstation antwortet nicht.",
                               "en": "The weather station is not answering."},

    # -- Konfiguration
    "weather.searching": {"de": "Ortssuche laeuft ...", "en": "Searching for the place ..."},
    "weather.search_empty": {"de": "Kein Ort gefunden.", "en": "No place found."},
    "weather.place_saved": {"de": "Ort gesetzt: {place}", "en": "Location set: {place}"},
    "weather.place_cleared": {"de": "Ort geloescht.", "en": "Location cleared."},
    "weather.clock_added": {"de": "Uhr ergaenzt: {zone}", "en": "Clock added: {zone}"},
    "weather.clock_removed": {"de": "Uhr entfernt: {zone}", "en": "Clock removed: {zone}"},
    "weather.clock_invalid": {"de": "Unbekannte Zeitzone (Beispiel: Europe/Zurich).",
                              "en": "Unknown time zone (example: Europe/Zurich)."},
}
