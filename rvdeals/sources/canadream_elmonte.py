"""CanaDream + El Monte RV joint Canada-to-US relocation program.

Both companies describe the same program on their own page: one shared offer paragraph
(rate, nights, pick-up window) and a heading per route ("Vancouver to Seattle").
We read both pages and merge them, so one route is one deal (no double texts).
"""
from __future__ import annotations

import re
from datetime import date

from ..models import Deal, NOT_LISTED
from ..textutil import MONTHS, clean, page_text, soup

ELMONTE_URL = "https://www.elmonterv.com/rv-rental-deal-canada-to-us-relocation"
CANADREAM_URL = "https://www.canadream.com/special-offers/canada-to-us-relocation/"
COMPANY = "CanaDream + El Monte RV"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _window(text: str):
    """'between October 15 30 and November 30, 2026' -> (Oct 30 2026, Nov 30 2026).
    When a start day is shown twice (an old date struck through), the last one wins."""
    m = re.search(r"between\s+([A-Za-z]+)\s+([\d\s]+?)\s+and\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if not m:
        return None, None, NOT_LISTED
    m1, m2 = MONTHS.get(m.group(1)[:3].lower()), MONTHS.get(m.group(3)[:3].lower())
    if not (m1 and m2):
        return None, None, NOT_LISTED
    d1 = int(m.group(2).split()[-1])
    year = int(m.group(5))
    start_year = year - 1 if m1 > m2 else year
    try:
        a, b = date(start_year, m1, d1), date(year, m2, int(m.group(4)))
    except ValueError:
        return None, None, NOT_LISTED
    return a, b, f"{a:%b} {a.day} to {b:%b} {b.day}, {b.year}"


def parse(html: str, today: date, link: str) -> list[Deal]:
    s = soup(html)
    text = page_text(html)
    offer = re.search(r"\$(\d+(?:\.\d+)?)\s*/\s*night for the first (\d+) nights\s*,?\s*then \$(\d+(?:\.\d+)?)\s*/\s*night", text)
    if not offer:
        raise ValueError("CanaDream/El Monte offer sentence not found: layout or wording changed")
    rate, nights, extra_rate = float(offer.group(1)), int(offer.group(2)), float(offer.group(3))
    start, end, window_text = _window(text)
    miles = re.search(r"free mileage allowances ranging from ([\d,]+) to ([\d,]+) miles", text, re.I)
    vehicle = re.search(r"Available on ([A-Za-z0-9 ]+? motorhomes)", text)
    border = re.search(r"\$(\d+) USD border fee", text)

    routes = []
    for h in s.find_all(["h1", "h2", "h3"]):
        t = clean(h.get_text(" "))
        if " to " in t and "relocation" not in t.lower() and len(t) < 60:
            o, d = t.split(" to ", 1)
            routes.append((clean(o), clean(d)))
    if not routes:
        raise ValueError("CanaDream/El Monte route headings not found: layout changed")

    deals = []
    for o, d in dict.fromkeys(routes):
        deal = Deal(company=COMPANY, deal_id=f"CDEM-{_slug(o)}-{_slug(d)}-{end.isoformat() if end else 'x'}",
                    origin=o, destination=d, link=link, pickup_from=start, pickup_to=end,
                    pickup_text=window_text, nights=nights, nightly_rate=rate, extra_night_rate=extra_rate,
                    currency=NOT_LISTED, vehicle=vehicle.group(1) if vehicle else NOT_LISTED)
        if miles:
            deal.notes.append(f"free miles vary by route: {miles.group(1)} to {miles.group(2)} miles "
                              "(this route's figure not listed)")
        if border:
            deal.notes.append(f"you must import the RV at a commercial US border crossing; ${border.group(1)} USD border fee")
        deal.notes.append("extra nights after the first ones: $%g/night" % extra_rate)
        deals.append(deal)
    return deals


def collect(fetcher, today: date, wanted, seen_ids: set[str], max_details: int) -> list[Deal]:
    merged: dict[str, Deal] = {}
    errors = []
    for url in (ELMONTE_URL, CANADREAM_URL):
        try:
            for d in parse(fetcher.get(url), today, url):
                merged.setdefault(d.deal_id, d)
        except Exception as e:   # one page failing is fine if the other works
            errors.append(f"{url}: {e}")
    if not merged and errors:
        raise RuntimeError("; ".join(errors))
    return [d for d in merged.values() if wanted(d) and d.deal_id not in seen_ids]
