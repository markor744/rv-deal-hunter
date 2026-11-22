"""Trip-plan pages for GitHub Pages (docs/). Public: only deal facts, never personal data."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from .geo import split_places
from .itinerary_data import CORRIDORS, I5, I5_SF_ONLY, W
from .models import Deal, NOT_LISTED
from .scoring import Score

KMH = 80          # typical RV pace including short stops
MAX_HOURS = 5.0
CHECK = "check before you go"


@dataclass
class Day:
    n: int
    start: str
    end: str
    km: float
    hours: float
    stops: list
    camp: str
    warnings: list
    start_key: str = ""
    end_key: str = ""


@dataclass
class RouteOption:
    name: str
    kind: str
    total_km: float
    days: list
    fits_hours: bool
    fits_cap: bool | None
    notes: list


def _path(corr: dict, o: str, d: str):
    pts = corr["points"]
    if corr is I5:   # San Francisco is a side branch of I-5: use it only as an end point
        drop = {"los banos", "los angeles", "san diego"} if I5_SF_ONLY in (o, d) else {I5_SF_ONLY}
        pts = [p for p in pts if p[0] not in drop]
    keys = [p[0] for p in pts]
    if o not in keys or d not in keys:
        return None
    i, j = keys.index(o), keys.index(d)
    if i == j:
        return None
    if i < j:
        seg = pts[i:j + 1]
        base = seg[0][2]
        return [(k, n, km - base, s, c, w) for (k, n, km, s, c, w) in seg]
    seg = list(reversed(pts[j:i + 1]))
    top = seg[0][2]
    return [(k, n, top - km, s, c, w) for (k, n, km, s, c, w) in seg]


def _cost(km: float) -> float:
    h = km / KMH
    return h * h + 30 * max(0.0, h - MAX_HOURS) ** 2


def _split(path, days: int) -> list[int]:
    """Choose the overnight stop index for each day (last = destination), keeping days even."""
    m = len(path) - 1
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(days + 1)]
    back = [[0] * (m + 1) for _ in range(days + 1)]
    dp[0][0] = 0.0
    for j in range(1, days + 1):
        for i in range(m + 1):
            for p in range(i + 1):
                if dp[j - 1][p] == INF:
                    continue
                c = dp[j - 1][p] + _cost(path[i][2] - path[p][2])
                if c < dp[j][i]:
                    dp[j][i], back[j][i] = c, p
    stops, i = [], m
    for j in range(days, 0, -1):
        stops.append(i)
        i = back[j][i]
    return list(reversed(stops))


def _longest(path, idx) -> float:
    prev, worst = 0, 0.0
    for i in idx:
        worst, prev = max(worst, path[i][2] - path[prev][2]), i
    return worst


def _months(deal: Deal, today: date) -> set[int]:
    start = deal.pickup_from or today
    span = (deal.nights or 7) + max(0, ((deal.pickup_to or start) - start).days)
    return {(start + timedelta(days=k)).month for k in range(0, span + 1, 5)} | {start.month}


def build_option(corr: dict, path, deal: Deal, today: date) -> RouteOption:
    total = path[-1][2]
    if deal.nights:
        days = deal.nights
        idx = _split(path, days)
    else:   # nights not listed: use the fewest days that keep each one under MAX_HOURS
        days = max(1, math.ceil(total / (KMH * MAX_HOURS)))
        idx = _split(path, days)
        while _longest(path, idx) / KMH > MAX_HOURS and days < 40:
            days += 1
            idx = _split(path, days)
    months = _months(deal, today)
    out, prev = [], 0
    for n, i in enumerate(idx, 1):
        a, b = path[prev], path[i]
        km = b[2] - a[2]
        warn_keys = list(dict.fromkeys(list(a[5]) + list(b[5]) + corr.get("always", [])))
        warns = [W[k][1] for k in warn_keys if months & W[k][0]]
        stops = b[3] if km > 0 else ["Rest day: explore around " + b[1]] + b[3][:1]
        out.append(Day(n, a[1], b[1], km, round(km / KMH * 2) / 2, stops[:3], b[4], warns, a[0], b[0]))
        prev = i
    fits_h = all(dd.hours <= MAX_HOURS for dd in out)
    cap = deal.included_distance_km
    fits_cap = None if cap is None else (cap == float("inf") or cap >= total)
    notes = []
    if not fits_h:
        notes.append(f"Some days are over {MAX_HOURS:g} hours of driving with {days} nights.")
    if cap not in (None, float("inf")):
        spare = cap - total
        notes.append(f"Distance cap {cap:,.0f} km vs about {total:,.0f} km of driving: "
                     + (f"about {spare:,.0f} km spare for side trips." if spare >= 0
                        else f"about {-spare:,.0f} km over the cap; expect excess charges ({deal.excess_rate})."))
    return RouteOption(corr["name"], corr["kind"], total, out, fits_h, fits_cap, notes)


def options_for(deal: Deal, today: date) -> list[RouteOption]:
    opts = []
    for o in split_places(deal.origin):
        for d in split_places(deal.destination):
            for corr in CORRIDORS:
                p = _path(corr, o, d)
                if p:
                    opts.append(build_option(corr, p, deal, today))
    seen, uniq = set(), []
    for op in opts:   # corridors that share the same stretch (e.g. Calgary onward) give one option
        key = tuple((d.start, d.end) for d in op.days)
        if key not in seen:
            seen.add(key)
            uniq.append(op)
    return uniq
