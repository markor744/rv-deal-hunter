"""Fraserway relocation specials (phone booking only: 1-800-661-2441).

The page is free text from their content system. When there are no deals it says
"Check back for new Relocation Specials." When deals are posted we look for
"<City> to <City>" lines; if we cannot read them, we still tell you the page changed
so you can call (one notice per change, never a guessed price).
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

from ..models import Deal, NOT_LISTED
from ..textutil import clean, money, parse_day_month, soup

URL = "https://rent.fraserway.com/en/rv/rental-specials/relocation-specials/"
PHONE = "1-800-661-2441"
COMPANY = "Fraserway"
EMPTY_MARKER = "check back for new relocation specials"
CITY = r"[A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+)?"


def _main_text(html: str) -> str:
    s = soup(html)
    main = s.find(id="rent-relocation-specials") or s.find(id="maincontent")
    if main is None:
        raise ValueError("Fraserway main content not found: layout changed")
    for t in main(["script", "style", "form", "svg"]):
        t.decompose()
    text = clean(main.get_text(" "))
    # drop the newsletter sign-up and everything after it
    cut = re.search(r"Get notified before everyone else|Become a Fraserway Adventurer", text)
    return text[:cut.start()] if cut else text


def parse(html: str, today: date) -> list[Deal]:
    text = _main_text(html)
    if EMPTY_MARKER in text.lower():
        return []
    deals = []
    for m in re.finditer(rf"({CITY})\s+(?:to|→|-)\s+({CITY})(.{{0,200}})", text):
        o, d, tail = m.group(1), m.group(2), m.group(3)
        if o.lower() in {"relocation", "rv", "specials"}:
            continue
        rate, cur = money(tail)
        when = parse_day_month(tail, today)
        nid = hashlib.sha1(f"{o}|{d}|{tail[:80]}".encode()).hexdigest()[:10]
        deals.append(Deal(company=COMPANY, deal_id=f"FW-{nid}", origin=o, destination=d, link=URL,
                          pickup_from=when, pickup_text=clean(tail[:80]) or NOT_LISTED,
                          nightly_rate=rate, currency=cur or NOT_LISTED,
                          booking=f"phone: {PHONE}", notes=["read from free text; confirm by phone"]))
    if not deals:
        nid = hashlib.sha1(text.encode()).hexdigest()[:10]
        deals.append(Deal(company=COMPANY, deal_id=f"FW-page-{nid}", origin=NOT_LISTED,
                          destination=NOT_LISTED, link=URL, booking=f"phone: {PHONE}",
                          notes=["Fraserway posted something new that this tool cannot read; call or check the page"]))
    return deals


def collect(fetcher, today: date, wanted, seen_ids: set[str], max_details: int) -> list[Deal]:
    out = []
    for d in parse(fetcher.get(URL), today):
        if d.deal_id in seen_ids:
            continue
        if d.origin == NOT_LISTED or wanted(d):
            out.append(d)
    return out
