"""CanaDream relocation specials: a plain HTML table (widget-relocation-offers)."""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urljoin

from ..models import Deal, NOT_LISTED
from ..textutil import clean, money, page_text, parse_day_month, soup

BASE = "https://www.canadream.com"
URL = f"{BASE}/special-offers/relocation-specials/"
COMPANY = "CanaDream"


def parse(html: str, today: date) -> list[Deal]:
    s = soup(html)
    widget = s.find(class_="widget-relocation-offers")
    if widget is None:
        raise ValueError("CanaDream relocation table not found: layout changed")
    table = widget.find("table")
    headers = [clean(th.get_text(" ")) for th in table.find_all("th")]
    if headers[:7] != ["From", "To", "Pick Up", "Drop Off", "RV Type", "Price", "Incl. Km"]:
        raise ValueError(f"CanaDream table headers changed: {headers}")

    text = page_text(html)
    m = re.search(r"Full payment at time of booking[^.]*\.", text)
    policy = m.group(0) if m else NOT_LISTED

    deals = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue
        c = [clean(td.get_text(" ")) for td in tds]
        a = tr.find("a", href=True)
        link = urljoin(BASE, a["href"]) if a else URL
        slug = a["href"].rstrip("/").split("/")[-1] if a else f"{c[0]}-{c[1]}-{c[2]}"
        pickup = parse_day_month(c[2], today)
        dropoff = parse_day_month(c[3], today)
        rate, cur = money(c[5])
        nm = re.search(r"up to (\d+) nights", c[5])
        km = re.search(r"[\d,]+", c[6])
        vehicles = " or ".join(clean(x) for x in tds[4].stripped_strings)
        d = Deal(company=COMPANY, deal_id=f"CD-{slug}", origin=c[0], destination=c[1], link=link,
                 pickup_from=pickup,
                 pickup_text=f"pick up from {c[2]}, return by {c[3]}",
                 nights=int(nm.group(1)) if nm else None,
                 currency=cur or "CAD (assumed: prices on CanaDream's Canadian site)",
                 nightly_rate=rate,
                 included_distance_km=float(km.group(0).replace(",", "")) if km else None,
                 vehicle=vehicles or NOT_LISTED, penalty_terms=policy)
        if pickup and dropoff and d.nights:
            latest = dropoff - timedelta(days=d.nights)
            if latest >= pickup:
                d.pickup_to = latest
                d.notes.append("latest pick-up worked out as return date minus nights")
        extras = c[7]
        if extras:
            d.notes.append(f"extras: {extras}")
        if "*" in c[5]:
            d.notes.append("site note: extra nights may be available at regular rates")
        deals.append(d)
    return deals


def collect(fetcher, today: date, wanted, seen_ids: set[str], max_details: int) -> list[Deal]:
    return [d for d in parse(fetcher.get(URL), today) if wanted(d) and d.deal_id not in seen_ids]
