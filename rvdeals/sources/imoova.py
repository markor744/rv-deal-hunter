"""Imoova: server-rendered HTML.

1. The table pages /relocations/table/usa and /relocations/table/canada list every current
   US and Canada relocation (ref, from, to, dates, vehicle, rate, nights, seats, fuel, ferry).
2. For deals on your routes that we have not seen before, we open the deal page for the
   fees, bond, distance allowance, fuel refund and sleeping capacity.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urljoin

from ..models import Deal, NOT_LISTED
from ..textutil import clean, money, page_text, parse_day_month, parse_range, soup

BASE = "https://www.imoova.com"
TABLE_URLS = [f"{BASE}/relocations/table/usa", f"{BASE}/relocations/table/canada"]
COMPANY = "Imoova"


def _nights(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"(\d+)\s*\+\s*(\d+)\s*nights?", text or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*nights?", text or "")
    return (int(m.group(1)), None) if m else (None, None)


def parse_table(html: str, today: date) -> list[Deal]:
    s = soup(html)
    table = s.find("table")
    if table is None:
        raise ValueError("Imoova table page has no <table>: layout changed")
    headers = [clean(th.get_text(" ")) for th in table.find_all("th")]
    need = {"Ref", "From", "To", "Depart", "Deliver", "Rate", "Duration"}
    if not need.issubset(headers):
        raise ValueError(f"Imoova table headers changed: {headers}")
    idx = {h: i for i, h in enumerate(headers)}
    deals = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < len(headers):
            continue
        cell = lambda h: clean(tds[idx[h]].get_text(" ")) if h in idx else ""
        ref = cell("Ref")
        a = tr.find("a", href=re.compile(r"/relocations/(usa|canada)/.+/RLC\d+"))
        link = urljoin(BASE, a["href"]) if a else f"{BASE}/relocations/{ref}"
        rate, cur = money(cell("Rate"))
        nights, extra = _nights(cell("Duration"))
        seats = re.search(r"\d+", cell("Seats"))
        fuel = cell("Fuel")
        ferry = cell("Ferry")
        d = Deal(company=COMPANY, deal_id=ref, origin=cell("From"), destination=cell("To"), link=link,
                 pickup_from=parse_day_month(cell("Depart"), today),
                 pickup_text=f"from {cell('Depart')}, deliver by {cell('Deliver')}",
                 nights=nights, extra_nights=extra, currency=cur or NOT_LISTED, nightly_rate=rate,
                 vehicle=cell("Vehicle") or NOT_LISTED)
        deliver = parse_day_month(cell("Deliver"), today)
        if deliver and nights and d.pickup_from and deliver - timedelta(days=nights) >= d.pickup_from:
            d.pickup_to = deliver - timedelta(days=nights)   # replaced by the deal page's own window
        d.notes.append(f"seats: {seats.group(0) if seats else NOT_LISTED}")
        d.fuel_text = "fuel allowance: yes (amount on deal page)" if fuel.lower() == "yes" else (
            "no fuel allowance" if fuel.lower() == "no" else NOT_LISTED)
        if fuel.lower() == "no":
            d.fuel_allowance = 0.0
        if ferry.lower() == "no":
            d.ferry_allowance = 0.0
        deals.append(d)
    return deals


def _after_heading(s, label: str) -> str:
    h = s.find(lambda t: t.name in ("h3", "h4", "dt", "span", "p", "div")
               and clean(t.get_text(" ")) == label)
    if not h:
        return ""
    nxt = h.find_next(["p", "dd", "span"])
    return clean(nxt.get_text(" ")) if nxt else ""


def _cost(text: str, label: str) -> tuple[float | None, str]:
    m = re.search(re.escape(label) + r"\s+((?:CA|US)?\$[\d,]+(?:\.\d+)?)", text)
    return money(m.group(1)) if m else (None, "")


def enrich(deal: Deal, html: str, today: date) -> Deal:
    """Fill fees, bond, distance, fuel and sleeps from a deal page."""
    s = soup(html)
    text = page_text(html)
    rate, cur = _cost(text, "Relocation rate")
    if rate is not None:
        deal.nightly_rate, deal.currency = rate, cur or deal.currency
    deal.extra_night_rate = _cost(text, "Extra night rate")[0]
    deal.booking_fee = _cost(text, "Booking fee")[0]
    deal.bond = _cost(text, "Bond")[0]
    deal.holding_deposit = _cost(text, "Holding deposit")[0]
    m = re.search(r"Excess mileage\s+((?:CA|US)?\$[\d.,]+\s*/\s*(?:km|mi|mile))", text)
    deal.excess_rate = m.group(1) if m else NOT_LISTED

    window = _after_heading(s, "Pickup between")
    if window:
        a, b = parse_range(window, today)
        deal.pickup_from, deal.pickup_to = a or deal.pickup_from, b
        deal.pickup_text = window
    nights, extra = _nights(_after_heading(s, "Duration"))
    if nights is not None:
        deal.nights, deal.extra_nights = nights, extra

    dist = _after_heading(s, "Distance")
    if re.search(r"unlimited", dist, re.I):
        deal.included_distance_km = float("inf")
    else:
        m = re.search(r"([\d,]+)\s*(km|mi|miles?)\b", dist, re.I)
        if m:
            n = float(m.group(1).replace(",", ""))
            deal.included_distance_km = n if m.group(2).lower() == "km" else round(n * 1.609)

    for icon, attr in (("lucide-fuel", "fuel"), ("lucide-ship", "ferry")):
        svg = s.find("svg", class_=icon)
        if not svg:
            continue
        box = svg.find_parent("li") or svg.find_parent("div")
        amount, _ = money(clean(box.get_text(" ")) if box else "")
        note = clean(box.find("p").get_text(" ")) if box and box.find("p") else ""
        if amount is not None:
            setattr(deal, f"{attr}_allowance", amount)
            if attr == "fuel":
                sym = "US$" if deal.currency == "USD" else "CA$" if deal.currency == "CAD" else "$"
                deal.fuel_text = f"{sym}{amount:,.0f}" + (f", {note[0].lower() + note[1:]}" if note else "")

    m = re.search(r"Sleeps\s+(\d+)", text)
    if m:
        deal.sleeps = int(m.group(1))
    m = re.search(r"(?:no[- ]show|late return|cancellation)[^.]{0,120}\$[\d,]+[^.]{0,60}", text, re.I)
    if m and "?" not in m.group(0):
        deal.penalty_terms = m.group(0)
    return deal


def collect(fetcher, today: date, wanted, seen_ids: set[str], max_details: int) -> list[Deal]:
    deals: list[Deal] = []
    for url in TABLE_URLS:
        deals.extend(parse_table(fetcher.get(url), today))
    unique = {d.deal_id: d for d in deals}
    out, opened = [], 0
    for d in unique.values():
        if not wanted(d) or d.deal_id in seen_ids:
            continue
        if opened < max_details:
            enrich(d, fetcher.get(d.link), today)
            opened += 1
            out.append(d)
        # deals beyond the cap wait for the next run (they stay unseen)
    return out
