"""Route matching and the 0-100 'good deal' score. All knobs live in config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from datetime import date

from .geo import norm, road_km, split_places
from .models import Deal, NOT_LISTED
from .travel import all_in, leg_for


@dataclass
class Score:
    total: int
    parts: dict = field(default_factory=dict)
    route_km: float | None = None
    real_cost_per_night_cad: float | None = None     # RV + fee only
    allin_per_night_cad: float | None = None         # the whole trip
    warnings: list[str] = field(default_factory=list)
    explain: list = field(default_factory=list)      # (rating, text): good / ok / bad / unknown, in plain words
    unknowns: int = 0
    flags: list = field(default_factory=list)        # short "why it's weak" labels, worst first


def _names(xs) -> set[str]:
    return {norm(x) for x in xs}


def route_matches(deal: Deal, cfg: dict) -> bool:
    r = cfg["routes"]
    ends = _names(r["end_in"])
    starts = _names(r["start_in"])
    return bool(set(split_places(deal.destination)) & ends or set(split_places(deal.origin)) & starts)


def _best_pair(deal: Deal, cfg: dict) -> tuple[str, str]:
    """For 'Toronto / Montreal' to 'Vancouver / Calgary / Edmonton', pick the pair that matters to you."""
    ends = _names(cfg["routes"]["end_in"])
    starts = _names(cfg["routes"]["start_in"])
    os_, ds = split_places(deal.origin) or [""], split_places(deal.destination) or [""]
    d = next((x for x in ds if x in ends), ds[0])
    o = next((x for x in os_ if x in starts), os_[0]) if d not in ends else os_[0]
    return o, d


def _cad(amount: float | None, deal: Deal, cfg: dict) -> float | None:
    if amount is None:
        return None
    return amount * cfg["scoring"]["usd_to_cad"] if deal.currency == "USD" else amount


def _lin(x: float, lo: float, hi: float) -> float:
    """0 at lo, 1 at hi (either direction), clamped."""
    if hi == lo:
        return 1.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


MOUNTAIN = {"bozeman", "denver", "salt lake city", "calgary", "edmonton", "kamloops", "kelowna", "whitehorse",
            "spokane", "boise", "missoula", "banff", "jasper", "anchorage", "reno", "penticton", "flagstaff"}
CASCADES_LON = -121.4    # west of this: the coast; a trip across it crosses the Cascades or Coast Mountains


def _crosses_mountains(places: list[str]) -> bool:
    from .geo import CITIES
    if any(p in MOUNTAIN for p in places):
        return True
    lons = [CITIES[p][1] for p in places if p in CITIES]
    return bool(lons) and min(lons) < CASCADES_LON < max(lons)


def _trip_dates(deal: Deal, today: date) -> list[date]:
    from datetime import timedelta
    start = max(deal.pickup_from or today, today)
    return [start + timedelta(days=k) for k in range(0, (deal.nights or 7) + 1, 3)]


WINTER_WORDS = ("winter", "snow", "chains", "avalanche", "blizzard", "icy", "extreme cold")
ASSUMED_FEE = 49.0     # when a site doesn't list its booking fee, assume a typical one instead of $0


def score(deal: Deal, cfg: dict, today: date) -> Score:
    """0-100. Every part is a real, explainable quantity; unknowns earn little, never full marks.

    value 50      all-in cost per night (RV + fee + flight/bus + fuel after refund + camping)
    pace 15       nights vs the days the drive needs at about 5 h a day
    distance 10   included distance vs the route
    timing 10     can you realistically pick it up
    season 10     snow, passes or blizzards on this route in these months
    sleeps 5      sleeps 2 or more
    priority +5   bonus when it starts in one of your priority cities (total capped at 100)
    """
    from .plans import KMH, MAX_HOURS, options_for          # late import: plans imports Score
    sc = cfg["scoring"]
    w = sc.get("weights", {})
    W = {k: w.get(k, v) for k, v in {"value": 50, "pace": 15, "distance": 10, "timing": 10, "season": 10,
                                       "sleeps": 5, "priority_origin": 5}.items()}
    parts: dict[str, float] = {}
    why: list[tuple[str, str]] = []
    warn: list[str] = []
    flags: list[tuple[float, str]] = []      # (points lost, short label)
    unknown = 0
    o, d = _best_pair(deal, cfg)
    rkm = road_km(o, d)

    # Timing first: a closed window is worth nothing, whatever else it offers.
    if deal.pickup_from is None:
        parts["timing"] = W["timing"] * 0.4
        why.append(("unknown", "Pick-up dates not listed"))
        unknown += 1
    else:
        a = (deal.pickup_from - today).days
        b = ((deal.pickup_to or deal.pickup_from) - today).days
        if b < 0:
            return Score(0, {"timing": 0}, rkm, warnings=["pick-up window has passed"],
                         explain=[("bad", "The pick-up window has closed")])
        if b < 2:
            parts["timing"] = W["timing"] * 0.2
            why.append(("bad", f"Pick-up closes in {b} day{'s' if b != 1 else ''}: only if you can leave now"))
        elif b < sc.get("pickup_min_days", 7):
            parts["timing"] = W["timing"] * 0.6
            why.append(("ok", f"Pick-up closes in {b} days: short notice"))
        elif a > sc.get("pickup_max_days", 120):
            parts["timing"] = W["timing"] * 0.7
            why.append(("ok", f"Pick-up is {a} days away: plans may change before then"))
        else:
            parts["timing"] = W["timing"]
            why.append(("good", f"Pick-up window is open for {b} more days"))

    # Value: the whole trip per night.
    cpn = allin_pn = None
    if deal.nightly_rate is not None and deal.nights:
        fee_known = deal.booking_fee is not None
        priced = deal if fee_known else replace(deal, booking_fee=ASSUMED_FEE)
        cpn = _cad((priced.nightly_rate * priced.nights + priced.booking_fee) / priced.nights, deal, cfg)
        cost = all_in(priced, cfg, leg_for(priced, cfg, today), rkm)
        allin_pn = (cost.low + cost.high) / 2 / deal.nights
        lo, hi = sc.get("value_full_night_cad", 80), sc.get("value_zero_night_cad", 300)
        frac = _lin(allin_pn, hi, lo)
        parts["value"] = W["value"] * frac
        if frac < 0.5:
            flags.append((W["value"] * (1 - frac), f"costs ~${allin_pn:,.0f} a night all-in"))
        why.append(("good" if frac >= 0.6 else "ok" if frac >= 0.25 else "bad",
                    f"About ${allin_pn:,.0f} a night all-in (RV, getting there or home, fuel, camping)"
                    + ("" if fee_known else f"; booking fee not listed, ${ASSUMED_FEE:.0f} assumed")))
        if not fee_known:
            warn.append("booking fee not listed")
            unknown += 1
    else:
        parts["value"] = W["value"] * 0.15
        why.append(("unknown", "Price or nights not listed, so the real cost is unknown"))
        unknown += 1

    # Pace: nights vs the days the drive needs.
    if deal.nights and rkm:
        need = max(1, math.ceil(rkm / (KMH * MAX_HOURS)))
        ratio = deal.nights / need
        parts["pace"] = W["pace"] * (0.0 if ratio < 0.85 else _lin(ratio, 0.85, 2.0))
        if ratio < 0.85:
            why.append(("bad", f"{deal.nights} nights for a ~{rkm:,.0f} km drive: rushed, long driving days"))
            flags.append((W["pace"], f"rushed: {deal.nights} nights for ~{rkm:,.0f} km"))
        elif ratio < 1.3:
            why.append(("ok", f"{deal.nights} nights for a ~{rkm:,.0f} km drive: enough, little spare time"))
        else:
            why.append(("good", f"{deal.nights} nights for a ~{rkm:,.0f} km drive: time to explore"))
        if deal.extra_nights:
            why.append(("ok", f"Up to {deal.extra_nights} more nights available at a higher rate"))
    else:
        parts["pace"] = W["pace"] * 0.3
        why.append(("unknown", "Can't tell if the nights fit the drive"))
        unknown += 1

    # Distance allowance.
    inc = deal.included_distance_km
    if inc == float("inf"):
        parts["distance"] = W["distance"]
        why.append(("good", "Unlimited distance"))
    elif inc is None or not rkm:
        parts["distance"] = W["distance"] * 0.3
        why.append(("unknown", "Distance allowance not listed"))
        unknown += 1
    else:
        ratio = inc / rkm
        parts["distance"] = 0.0 if ratio < 1.0 else W["distance"] * _lin(ratio, 1.0, 1.2) * 0.4 + W["distance"] * 0.6
        if ratio < 1.0:
            why.append(("bad", f"Only {inc:,.0f} km included for a ~{rkm:,.0f} km drive: you'd pay for the rest"))
            warn.append(f"distance cap {inc:,.0f} km is less than the ~{rkm:,.0f} km route")
            flags.append((W["distance"], "distance cap shorter than the route"))
        else:
            why.append(("good" if ratio >= 1.15 else "ok", f"{inc:,.0f} km included for a ~{rkm:,.0f} km drive"))

    # Season and roads for the months of this trip.
    opts = options_for(deal, today)
    if opts:
        best = next((x for x in opts if x.fits_hours), opts[0])
        alerts = {w_ for dd in best.days for w_ in dd.warnings}
        winter = [a_ for a_ in alerts if any(k in a_.lower() for k in WINTER_WORDS)]
        if winter:
            parts["season"] = W["season"] * 0.3
            why.append(("bad", "Winter driving likely on this route then (snow, passes or closures)"))
            flags.append((W["season"] * 0.7, "winter roads"))
        elif any("heat" in a_.lower() or "wildfire" in a_.lower() for a_ in alerts):
            parts["season"] = W["season"] * 0.8
            why.append(("ok", "Summer heat or wildfire smoke possible on this route"))
        else:
            parts["season"] = W["season"]
            why.append(("good", "No seasonal road worries for these dates"))
    else:
        months = {m.month for m in _trip_dates(deal, today)}
        os_, ds = split_places(deal.origin), split_places(deal.destination)
        crosses = _crosses_mountains(os_ + ds)
        if months & {11, 12, 1, 2, 3} and crosses:
            parts["season"] = W["season"] * 0.3
            why.append(("bad", "Winter driving likely: this route crosses mountain passes in the snowy months"))
            flags.append((W["season"] * 0.7, "winter mountain passes"))
        else:
            parts["season"] = W["season"] * 0.7
            why.append(("ok", "No route plan for this trip, so road conditions are only roughly checked"))

    # Sleeps.
    if deal.sleeps is None:
        parts["sleeps"] = W["sleeps"] * 0.4
        why.append(("unknown", "Sleeping capacity not listed"))
        unknown += 1
    else:
        ok = deal.sleeps >= sc.get("min_sleeps", 2)
        parts["sleeps"] = W["sleeps"] if ok else 0.0
        why.append(("good" if ok else "bad", f"Sleeps {deal.sleeps}"))

    # Priority origin.
    pri = bool(set(split_places(deal.origin)) & _names(cfg["routes"]["priority_origins"]))
    parts["priority_origin"] = W["priority_origin"] if pri else 0.0
    if pri:
        why.append(("good", "Starts in one of your priority cities"))

    total = int(round(sum(parts.values())))
    order = {"bad": 0, "ok": 1, "good": 2, "unknown": 3}
    return Score(total=max(0, min(100, total)), parts={k: round(v, 1) for k, v in parts.items()},
                 route_km=rkm, real_cost_per_night_cad=cpn, allin_per_night_cad=allin_pn, warnings=warn,
                 explain=sorted(why, key=lambda r: order[r[0]]), unknowns=unknown,
                 flags=[f for _, f in sorted(flags, key=lambda x: -x[0])])


def tier(total: int, cfg: dict) -> str:
    t = cfg["thresholds"]
    if total >= t["text_now"]:
        return "now"
    if total >= t["digest"]:
        return "digest"
    return "log"
