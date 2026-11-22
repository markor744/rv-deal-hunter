"""Builds the text messages: plain ASCII, no emojis, at most 300 characters (2 SMS segments)."""
from __future__ import annotations

import re
import unicodedata

from .geo import split_places
from .models import Deal, NOT_LISTED
from .scoring import Score
from .travel import money, range_text

MAX_CHARS = 300
SHORT = {"los angeles": "LA", "san francisco": "SF", "san diego": "San Diego", "las vegas": "Vegas",
         "vancouver": "Vancouver", "seattle": "Seattle"}


def ascii_only(s: str) -> str:
    s = s.replace("\u2192", ">").replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()


def place(text: str) -> str:
    names = split_places(text)
    if not names:
        return text
    shown = [SHORT.get(n, n.title()) for n in names]
    return "/".join(shown) if len(shown) <= 2 else f"{shown[0]} etc"


def _money(v: float | None, cur: str) -> str:
    if v is None:
        return "?"
    sym = "US$" if cur == "USD" else "$"
    return f"{sym}{v:,.0f}" if v >= 10 or v == int(v) else f"{sym}{v:,.2f}"


def _window(d: Deal) -> str:
    a, b = d.pickup_from, d.pickup_to
    if a and b and a != b:
        return f"{a:%b} {a.day}-{b.day}" if a.month == b.month else f"{a:%b} {a.day}-{b:%b} {b.day}"
    if a:
        return f"from {a:%b} {a.day}"
    return "dates not listed"


def plan_url(base: str, d: Deal) -> str:
    return f"{base.rstrip('/')}/p/{d.deal_id}.html"


def word(total: int) -> str:
    return "Great" if total >= 70 else "Good" if total >= 40 else "Weak"


def _leg_bit(leg) -> str:
    if not leg or (leg.low == 0 and leg.high == 0):
        return ""
    what = ("flight there" if leg.direction == "there" else "flight home") if leg.mode == "fly" else (
        "bus/ferry there" if leg.direction == "there" else "bus/ferry home")
    return f"{what} {range_text(leg.low, leg.high)}"


def alert(d: Deal, s: Score, plans_base: str, allin=None, leg=None) -> str:
    """Plain-English alert, one link. Example:
    RV DEAL 82/100 Great: LA > Vancouver. Pick up Mar 3-8, 7 nights. All-in about $520-680
    (RV $56, flight there $160-320, fuel+camping $310). Watch: $2,330 bond. Details + book: <link>"""
    route = f"{place(d.origin)} > {place(d.destination)}"
    nights = f"{d.nights} nights" if d.nights else "nights not listed"
    head = f"RV DEAL {s.total}/100 {word(s.total)}: {route}. Pick up {_window(d)}, {nights}."

    money_long = money_short = ""
    if allin:
        parts = [f"RV {range_text(allin.rv, allin.rv)}"]
        lb = _leg_bit(leg)
        if lb:
            parts.append(lb)
        parts.append(f"fuel+camping {range_text(allin.fuel + allin.camping, allin.fuel + allin.camping)}")
        approx = "about " if allin.complete else "roughly "
        money_short = f" All-in {approx}{range_text(allin.low, allin.high)}."
        money_long = money_short[:-1] + f" ({', '.join(parts)})."
    elif d.nightly_rate is not None:
        money_short = money_long = f" {_money(d.nightly_rate, d.currency)}/night" + (
            f" + {_money(d.booking_fee, d.currency)} fee." if d.booking_fee else ".")

    watch = []
    if d.bond:
        watch.append(f"{_money(d.bond, d.currency)} bond")
    if d.penalty_terms != NOT_LISTED:
        watch.append(ascii_only(d.penalty_terms)[:50])
    watch.extend(w for w in s.warnings if "booking fee" not in w)
    plan = plan_url(plans_base, d)
    tail = (f" Call {d.booking.split(': ', 1)[1]} to book. Details: {plan}" if d.booking.startswith("phone")
            else f" Details + book: {plan}")

    for money in (money_long, money_short):
        for n in range(len(watch), -1, -1):
            w = (" Watch: " + ", ".join(watch[:n]) + ".") if n else ""
            c = ascii_only(head + money + w + tail)
            if len(c) <= MAX_CHARS:
                return c
    return ascii_only(f"RV DEAL {s.total}/100: {route}.{tail}")[:MAX_CHARS]


def _short_when(d: Deal, today) -> str:
    a, b = d.pickup_from, d.pickup_to
    if a and b and a < today:
        return f"by {b:%b} {b.day}"
    return f"{a:%b} {a.day}" if a else "date ?"


def digest(items: list[tuple[Deal, Score]], plans_base: str, today=None, title: str = "RV deals digest") -> str:
    """One text for the 40-69 deals: compact lines, then one link to the page listing them all."""
    from datetime import date as _date
    today = today or _date.today()
    items = sorted(items, key=lambda x: -x[1].total)
    tail = f" All + plans: {plans_base.rstrip('/')}/"
    msg = f"{title} ({len(items)}):"
    shown = 0
    for d, s in items:
        when = _short_when(d, today)
        cost = (f"~{money(d._allin_low)} all-in" if getattr(d, "_allin_low", None)
                else f"{_money(d.nightly_rate, d.currency)}/n")
        line = f" {s.total} {place(d.origin)}>{place(d.destination)} {when}, {d.nights or '?'}n {cost};"
        more = len(items) - shown - 1
        extra = f" +{more} more." if more else ""
        if len(ascii_only(msg + line + extra + tail)) > MAX_CHARS:
            break
        msg += line
        shown += 1
    if shown < len(items):
        msg += f" +{len(items) - shown} more."
    return ascii_only(msg.rstrip(";") + tail)[:MAX_CHARS]
