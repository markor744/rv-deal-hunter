"""City names, aliases and APPROXIMATE driving distances.

Distances are estimates for scoring only (straight-line distance x a road factor, or a
rounded typical driving distance for common pairs). They are labelled approximate everywhere.
"""
from __future__ import annotations

import math
import re

# name -> (lat, lon)
CITIES = {
    "vancouver": (49.28, -123.12), "abbotsford": (49.05, -122.30), "victoria": (48.43, -123.37),
    "bellingham": (48.75, -122.48), "seattle": (47.61, -122.33), "everett": (47.98, -122.20),
    "calgary": (51.05, -114.07), "edmonton": (53.55, -113.49), "toronto": (43.65, -79.38),
    "montreal": (45.50, -73.57), "halifax": (44.65, -63.57), "whitehorse": (60.72, -135.06),
    "los angeles": (34.05, -118.24), "san diego": (32.72, -117.16), "san francisco": (37.77, -122.42),
    "las vegas": (36.17, -115.14), "phoenix": (33.45, -112.07), "denver": (39.74, -104.99),
    "portland": (45.52, -122.68), "salt lake city": (40.76, -111.89), "elkhart": (41.68, -85.98),
    "bozeman": (45.68, -111.04), "dallas": (32.78, -96.80), "chicago": (41.88, -87.63),
    "new york": (40.71, -74.01), "orlando": (28.54, -81.38), "boston": (42.36, -71.06),
    "atlanta": (33.75, -84.39), "kelowna": (49.89, -119.50), "kamloops": (50.67, -120.33),
    "nanaimo": (49.17, -123.94), "penticton": (49.49, -119.59), "spokane": (47.66, -117.43),
    "sacramento": (38.58, -121.49), "reno": (39.53, -119.81), "boise": (43.62, -116.20),
    "winnipeg": (49.90, -97.14), "regina": (50.45, -104.62), "saskatoon": (52.13, -106.67),
    "ottawa": (45.42, -75.70), "anchorage": (61.22, -149.90), "white rock": (49.03, -122.80),
    "federal way": (47.32, -122.31), "nashville": (36.16, -86.78), "moses lake": (47.13, -119.28), "port angeles": (48.12, -123.43),
}

ALIASES = {
    "la": "los angeles", "lax": "los angeles", "sf": "san francisco", "san fran": "san francisco",
    "vegas": "las vegas", "yvr": "vancouver", "seattle everett": "seattle", "seattle-everett": "seattle",
    "montréal": "montreal", "vancouver british columbia": "vancouver", "vancouver bc": "vancouver",
    "calgary alberta": "calgary", "edmonton alberta": "edmonton",
}

# Rounded typical driving distances in km (approximate; check a map before you go).
ROAD_KM = {
    ("los angeles", "vancouver"): 2060, ("los angeles", "seattle"): 1840,
    ("san diego", "vancouver"): 2260, ("san diego", "seattle"): 2030,
    ("san francisco", "vancouver"): 1530, ("san francisco", "seattle"): 1300,
    ("las vegas", "seattle"): 1960, ("las vegas", "vancouver"): 2190,
    ("phoenix", "seattle"): 2440, ("phoenix", "vancouver"): 2670,
    ("calgary", "vancouver"): 970, ("edmonton", "vancouver"): 1160,
    ("calgary", "seattle"): 1150, ("edmonton", "seattle"): 1340,
    ("toronto", "vancouver"): 4400, ("montreal", "vancouver"): 4800,
    ("elkhart", "vancouver"): 3500, ("elkhart", "seattle"): 3400,
    ("vancouver", "seattle"): 230, ("halifax", "toronto"): 1790,
    ("calgary", "denver"): 1850, ("vancouver", "los angeles"): 2060,
}
ROAD_FACTOR = 1.25


def norm(name: str) -> str:
    """'Vancouver, British Columbia' / 'Seattle-Everett' -> 'vancouver' / 'seattle'."""
    s = (name or "").lower().strip()
    s = re.sub(r"[,()]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in ALIASES:
        return ALIASES[s]
    if s in CITIES:
        return s
    for city in sorted(CITIES, key=len, reverse=True):   # longest first: "white rock" before "rock"
        if re.search(rf"\b{re.escape(city)}\b", s):
            return city
    return s


def split_places(text: str) -> list[str]:
    """'Toronto / Montreal' -> ['toronto', 'montreal']."""
    return [norm(p) for p in re.split(r"\s*/\s*|\s+or\s+", text or "") if p.strip()]


def _haversine(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def road_km(origin: str, destination: str) -> float | None:
    """Approximate driving km between two places, or None if a city is unknown."""
    o, d = norm(origin), norm(destination)
    if (o, d) in ROAD_KM:
        return float(ROAD_KM[(o, d)])
    if (d, o) in ROAD_KM:
        return float(ROAD_KM[(d, o)])
    if o in CITIES and d in CITIES:
        return round(_haversine(CITIES[o], CITIES[d]) * ROAD_FACTOR)
    return None
