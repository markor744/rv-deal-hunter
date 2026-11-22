"""Getting to the pick-up (or home from the drop-off), and the all-in trip cost.

Fares are ROUGH typical one-way economy fares from Vancouver (YVR), in CAD, for booking a few
weeks ahead. They are not quotes: every page says so and links to Google Flights for today's
real prices. Edit or add fares under `travel: fare_overrides:` in config.yaml.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote

from .geo import CITIES, norm, road_km, split_places
from .models import Deal

# city -> (airport code, airport city name for search)
AIRPORTS = {
    "los angeles": "LAX", "san diego": "SAN", "san francisco": "SFO", "las vegas": "LAS", "phoenix": "PHX",
    "calgary": "YYC", "edmonton": "YEG", "toronto": "YYZ", "montreal": "YUL", "denver": "DEN",
    "halifax": "YHZ", "portland": "PDX", "salt lake city": "SLC", "chicago": "ORD", "elkhart": "SBN",
    "bozeman": "BZN", "nashville": "BNA", "atlanta": "ATL", "dallas": "DFW", "new york": "JFK",
    "boston": "BOS", "orlando": "MCO", "winnipeg": "YWG", "regina": "YQR", "saskatoon": "YXE",
    "ottawa": "YOW", "whitehorse": "YXY", "kelowna": "YLW", "kamloops": "YKA", "anchorage": "ANC",
    "reno": "RNO", "sacramento": "SMF", "boise": "BOI", "spokane": "GEG", "penticton": "YYF",
    "seattle": "SEA", "bellingham": "BLI", "victoria": "YYJ", "nanaimo": "YCD",
}

# Rough one-way fares from YVR, CAD (low, high). Not quotes.
FARES = {
    "LAX": (160, 320), "SAN": (180, 350), "SFO": (150, 300), "LAS": (140, 300), "PHX": (170, 350),
    "YYC": (100, 250), "YEG": (110, 260), "YYZ": (200, 420), "YUL": (230, 450), "DEN": (200, 380),
    "YHZ": (280, 520), "PDX": (150, 300), "SLC": (200, 380), "ORD": (230, 420), "SBN": (280, 480),
    "BZN": (250, 450), "BNA": (250, 450), "ATL": (260, 450), "DFW": (230, 420), "JFK": (250, 450),
    "BOS": (270, 480), "MCO": (260, 450), "YWG": (160, 320), "YQR": (180, 350), "YXE": (180, 350),
    "YOW": (230, 430), "YXY": (250, 450), "YLW": (100, 220), "YKA": (120, 250), "ANC": (300, 550),
    "RNO": (220, 400), "SMF": (200, 360), "BOI": (220, 400), "GEG": (160, 320), "YYF": (150, 300),
}

# Time of year. Multipliers on the fares above (1.0 = an ordinary month), by travel month.
SEASON_FARE = {1: 0.85, 2: 0.9, 3: 1.1, 4: 0.95, 5: 1.0, 6: 1.15, 7: 1.3, 8: 1.25, 9: 1.0, 10: 0.9,
               11: 0.85, 12: 1.15}
HOLIDAY_FARE = 1.4                       # Dec 18 to Jan 5
SUN_AIRPORTS = {"LAX", "SAN", "PHX", "LAS", "SFO"}
SUN_WINTER_BUMP = 1.1                    # Vancouver to the sun is busier Dec to Apr
MONTH_NOTE = {1: "January (quiet)", 2: "February", 3: "March (spring break)", 4: "April", 5: "May",
              6: "June (summer)", 7: "July (peak summer)", 8: "August (peak summer)", 9: "September",
              10: "October", 11: "November (quiet)", 12: "December"}
# Campgrounds (CAD a night) and fuel (multiplier on fuel_cad_per_litre) by month.
CAMP_BY_MONTH = {6: 55, 7: 60, 8: 60, 5: 45, 9: 45}       # other months: 35 (fewer open, cheaper)
CAMP_OFF_SEASON = 35
FUEL_BY_MONTH = {6: 1.05, 7: 1.07, 8: 1.06, 12: 0.97, 1: 0.96, 2: 0.97}


def fare_factor(code: str, when: date | None, cfg: dict | None = None) -> tuple[float, str]:
    """(multiplier, note) for flying on that date."""
    if not when:
        return 1.0, ""
    custom = ((cfg or {}).get("travel") or {}).get("season_fare") or {}
    f = float(custom.get(when.month, SEASON_FARE[when.month]))
    note = MONTH_NOTE[when.month]
    if (when.month == 12 and when.day >= 18) or (when.month == 1 and when.day <= 5):
        f, note = HOLIDAY_FARE, "holidays"
    if code in SUN_AIRPORTS and when.month in (12, 1, 2, 3, 4):
        f *= SUN_WINTER_BUMP
        note += ", sun season"
    return f, note


# Places close enough to Vancouver that you take a bus, train, ferry or car instead of flying.
GROUND = {
    "vancouver": ("You're home", 0, 0, 0),
    "abbotsford": ("Drive or transit, about 1 h", 10, 30, 1.0),
    "white rock": ("Drive or transit, about 1 h", 10, 30, 1.0),
    "bellingham": ("Bus or car, about 1.5 h plus the border", 25, 60, 1.5),
    "seattle": ("Bus or Amtrak Cascades train, about 4 h", 40, 90, 4.0),
    "portland": ("Amtrak Cascades train or bus, about 8 h", 60, 120, 8.0),
    "everett": ("Bus or Amtrak Cascades train, about 3.5 h", 40, 90, 3.5),
    "victoria": ("BC Ferries plus bus, about 3.5 h", 25, 50, 3.5),
    "nanaimo": ("BC Ferries plus bus, about 2.5 h", 25, 50, 2.5),
}
HOME_AREA = {"vancouver", "abbotsford", "white rock", "bellingham", "seattle", "everett", "victoria"}


@dataclass
class Leg:
    direction: str        # "there" (get to pick-up) or "back" (home from drop-off)
    mode: str             # "fly" or "ground"
    place: str            # city name you travel to / from
    when: date | None
    low: float            # CAD
    high: float
    hours: float | None
    summary: str
    link: str | None
    season: str = ""      # e.g. "March (spring break)": what the fare estimate assumes


def _city_name(key: str) -> str:
    return key.title().replace("Ste ", "Ste. ")


def _fly_hours(a: str, b: str) -> float | None:
    if a in CITIES and b in CITIES:
        (la1, lo1), (la2, lo2) = CITIES[a], CITIES[b]
        p1, p2 = math.radians(la1), math.radians(la2)
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
        km = 6371 * 2 * math.asin(math.sqrt(h))
        return round((0.6 + km / 800) * 4) / 4        # taxi/climb + cruise, nearest 15 min
    return None


def flights_link(frm: str, to: str, when: date | None) -> str:
    q = f"Flights from {frm} to {to} one way" + (f" on {when.isoformat()}" if when else "")
    return "https://www.google.com/travel/flights?q=" + quote(q)


def _pick_city(text: str, prefer_far: bool) -> str:
    """For 'Vancouver / Calgary / Edmonton' pick the one that matters (home-area city if any)."""
    places = split_places(text) or [norm(text)]
    home = [p for p in places if p in HOME_AREA]
    far = [p for p in places if p not in HOME_AREA]
    return (far or home)[0] if prefer_far else (home or far)[0]


def leg_for(deal: Deal, cfg: dict, today: date) -> Leg | None:
    t = cfg.get("travel", {})
    home_code = t.get("home_airport", "YVR")
    overrides = t.get("fare_overrides") or {}
    o_all, d_all = split_places(deal.origin), split_places(deal.destination)
    ends_home = any(p in HOME_AREA for p in d_all)
    starts_home = any(p in HOME_AREA for p in o_all)
    if ends_home and not starts_home:
        direction, city = "there", _pick_city(deal.origin, prefer_far=True)
        start = max(deal.pickup_from or today, today + timedelta(days=7))
        when = start if not deal.pickup_to or start <= deal.pickup_to else deal.pickup_to
    elif starts_home and not ends_home:
        direction, city = "back", _pick_city(deal.destination, prefer_far=True)
        start = max(deal.pickup_from or today, today)
        when = start + timedelta(days=deal.nights or 7)
    elif starts_home and ends_home:
        direction, city = "back", _pick_city(deal.destination, prefer_far=False)
        when = max(deal.pickup_from or today, today) + timedelta(days=deal.nights or 3)
    else:
        return None
    if city in GROUND:
        text, low, high, hours = GROUND[city]
        if low == 0:
            return Leg(direction, "ground", _city_name(city), when, 0, 0, 0, "You're already home", None)
        return Leg(direction, "ground", _city_name(city), when, low, high, hours, text, None)
    code = AIRPORTS.get(city)
    if not code:
        return Leg(direction, "fly", _city_name(city), when, 0, 0, None,
                   f"Flight to {_city_name(city)}: price not estimated", flights_link(home_code, _city_name(city), when))
    low, high = overrides.get(code) or FARES.get(code) or (0, 0)
    f, note = fare_factor(code, when, cfg)
    low, high = round(low * f / 5) * 5, round(high * f / 5) * 5
    hours = _fly_hours("vancouver", city)
    frm, to = (home_code, code) if direction == "there" else (code, home_code)
    return Leg(direction, "fly", _city_name(city), when, low, high, hours,
               f"Flight {frm} to {to}", flights_link(frm, to, when), note)


@dataclass
class AllIn:
    rv: float            # CAD paid to the company up front
    travel: tuple        # (low, high) CAD
    fuel: float          # CAD, after the fuel refund
    fuel_gross: float
    camping: float
    low: float
    high: float
    complete: bool       # every part known (booking fee, route distance)
    route_km: float | None
    camp_per_night: float = 0
    month: int = 0
    style: str = "mix"
    by_style: dict = None     # style -> {"paid_nights", "camping", "low", "high"}
    people: int = 1
    leg_each: tuple = (0, 0)  # flight or bus per person (low, high)

    def model(self, nights: int) -> dict:
        """Everything a page needs to recalculate the all-in cost when you change Settings."""
        return {"rv": round(self.rv, 2), "tl": self.leg_each[0], "th": self.leg_each[1], "fuel": round(self.fuel, 2),
                "n": nights, "cpn": self.camp_per_night, "dc": self.style, "dp": self.people,
                "paid": {k: v["paid_nights"] for k, v in self.by_style.items()}}


def all_in(deal: Deal, cfg: dict, leg: Leg | None, route_km: float | None = None) -> AllIn | None:
    if deal.nightly_rate is None or not deal.nights:
        return None
    c = cfg.get("costs", {})
    fx = cfg["scoring"]["usd_to_cad"] if deal.currency == "USD" else 1.0
    rv = (deal.nightly_rate * deal.nights + (deal.booking_fee or 0)) * fx
    if route_km is None:
        os_, ds = split_places(deal.origin), split_places(deal.destination)
        dist = [road_km(o, d) for o in os_ for d in ds]
        dist = [x for x in dist if x]
        route_km = min(dist) if dist else None
    month = (deal.pickup_from or (leg.when if leg else None) or date.today()).month
    fuel_gross = ((route_km or 0) / 100 * c.get("rv_litres_per_100km", 28) * c.get("fuel_cad_per_litre", 1.70)
                  * FUEL_BY_MONTH.get(month, 1.0))
    refund = ((deal.fuel_allowance or 0) + (deal.ferry_allowance or 0)) * fx
    fuel = max(0.0, fuel_gross - refund)
    per_night = c.get("campground_cad_per_night")
    if per_night is None or per_night == "auto":
        per_night = CAMP_BY_MONTH.get(month, CAMP_OFF_SEASON)
    people = max(1, int((cfg.get("travel") or {}).get("travellers", 1)))
    el, eh = (leg.low, leg.high) if leg else (0, 0)
    tl, th = el * people, eh * people          # flights and buses are per person
    base_low, base_high = rv + tl + fuel, rv + th + fuel
    by_style = {}
    for style in CAMPING_STYLES:
        paid = paid_nights(deal.nights, style)
        camp = paid * float(per_night)
        by_style[style] = {"paid_nights": paid, "camping": camp, "low": base_low + camp, "high": base_high + camp}
    style = c.get("camping_style", "free")
    if style not in by_style:
        style = "free"
    s = by_style[style]
    complete = deal.booking_fee is not None and route_km is not None and (leg is None or leg.high > 0 or leg.low == 0)
    return AllIn(rv, (tl, th), fuel, fuel_gross, s["camping"], s["low"], s["high"],
                 complete, route_km, float(per_night), month, style, by_style, people, (el, eh))


# How you sleep. "free" still pays one night in four: a site with showers, water and a dump station.
CAMPING_STYLES = {
    "campgrounds": "Campgrounds every night",
    "mix": "Mix: about half the nights free",
    "free": "Mostly free, a paid site every 4th night",
}


def paid_nights(nights: int, style: str) -> int:
    if style == "campgrounds":
        return nights
    if style == "mix":
        return (nights + 1) // 2
    return nights // 4


def money(v: float) -> str:
    return f"${round(v / 10) * 10:,.0f}" if v >= 100 else f"${v:,.0f}"


def range_text(low: float, high: float) -> str:
    if round(low / 10) == round(high / 10):
        return money(low)
    return f"{money(low)}-{money(high)[1:]}"
