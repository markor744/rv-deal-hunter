"""Parse the saved pages (snapshots from 2026-11-22). If a site changes its layout,
the live run fails loudly and these tests show which reader needs updating."""
from datetime import date
from pathlib import Path

import pytest

from rvdeals.models import NOT_LISTED
from rvdeals.sources import canadream, canadream_elmonte, fraserway, imoova

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 22)


def read(name):
    return (FIX / name).read_text()


def test_imoova_table_lists_every_row():
    usa = imoova.parse_table(read("imoova_table_usa.html"), TODAY)
    ca = imoova.parse_table(read("imoova_table_canada.html"), TODAY)
    assert len(usa) == 93 and len(ca) == 14
    d = next(x for x in ca if x.deal_id == "RLC131780")
    assert (d.origin, d.destination) == ("Calgary", "Vancouver")
    assert d.pickup_from == date(2026, 11, 23)
    assert (d.nights, d.extra_nights) == (3, 3)
    assert d.nightly_rate == 1.0 and d.currency == "CAD"
    assert d.link.endswith("/relocations/canada/calgary-to-vancouver-british-columbia/RLC131780")


def test_imoova_deal_page_cad():
    d = next(x for x in imoova.parse_table(read("imoova_table_canada.html"), TODAY) if x.deal_id == "RLC131780")
    imoova.enrich(d, read("imoova_deal_RLC131780.html"), TODAY)
    assert d.booking_fee == 49.0 and d.bond == 5000.0 and d.holding_deposit == 100.0
    assert d.extra_night_rate == 49.0
    assert d.included_distance_km == 1500
    assert d.excess_rate == "CA$0.47 / km"
    assert d.fuel_allowance == 150.0 and "receipts" in d.fuel_text
    assert d.sleeps == 4
    assert (d.pickup_from, d.pickup_to) == (date(2026, 11, 23), date(2026, 12, 2))


def test_imoova_deal_page_usd_unlimited():
    d = next(x for x in imoova.parse_table(read("imoova_table_usa.html"), TODAY) if x.deal_id == "RLC130667")
    imoova.enrich(d, read("imoova_deal_RLC130667.html"), TODAY)
    assert d.currency == "USD" and d.booking_fee == 99.0 and d.bond == 2330.0
    assert d.included_distance_km == float("inf")
    assert (d.pickup_from, d.pickup_to) == (date(2027, 4, 1), date(2027, 4, 24))
    assert (d.nights, d.extra_nights) == (8, 10)


def test_canadream_table():
    deals = canadream.parse(read("canadream_relocation.html"), TODAY)
    assert len(deals) == 3
    d = next(x for x in deals if x.nightly_rate == 49.0)
    assert d.origin == "Toronto / Montreal" and "Vancouver" in d.destination
    assert d.pickup_from == date(2027, 3, 1) and d.nights == 21
    assert d.included_distance_km == 5000
    assert d.booking_fee is None and d.show("booking_fee") == NOT_LISTED   # never invented
    assert d.penalty_terms.startswith("Full payment at time of booking")


@pytest.mark.parametrize("fixture,url", [
    ("elmonte_canada_to_us.html", canadream_elmonte.ELMONTE_URL),
    ("canadream_canada_to_us.html", canadream_elmonte.CANADREAM_URL),
])
def test_canadream_elmonte_program(fixture, url):
    deals = canadream_elmonte.parse(read(fixture), TODAY, url)
    routes = {(d.origin, d.destination) for d in deals}
    assert ("Vancouver", "Seattle") in routes and ("Vancouver", "Los Angeles") in routes
    d = next(x for x in deals if x.destination == "Seattle")
    assert (d.nightly_rate, d.nights, d.extra_night_rate) == (1.0, 7, 99.0)
    assert d.pickup_to == date(2026, 11, 30)
    assert d.included_distance_km is None      # range given, not per route: not listed


def test_both_joint_pages_give_the_same_ids():
    a = {d.deal_id for d in canadream_elmonte.parse(read("elmonte_canada_to_us.html"), TODAY, "a")}
    b = {d.deal_id for d in canadream_elmonte.parse(read("canadream_canada_to_us.html"), TODAY, "b")}
    assert a == b


def test_fraserway_empty_page_has_no_deals():
    assert fraserway.parse(read("fraserway_empty.html"), TODAY) == []


def test_fraserway_new_content_gives_a_notice_not_a_guess():
    html = read("fraserway_empty.html").replace("Check back for new Relocation Specials.", "Spring specials coming, call us")
    deals = fraserway.parse(html, TODAY)
    assert len(deals) == 1 and deals[0].origin == NOT_LISTED and deals[0].nightly_rate is None


def test_layout_change_is_reported():
    with pytest.raises(ValueError):
        canadream.parse("<html><body>new design</body></html>", TODAY)
    with pytest.raises(ValueError):
        imoova.parse_table("<html><body>new design</body></html>", TODAY)
