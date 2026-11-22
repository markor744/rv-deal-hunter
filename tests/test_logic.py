"""Scoring, messages, the daily cap, no-repeat texts, scheduling slots and plan pages."""
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from rvdeals import message, pages, plans, sms
from rvdeals.main import Runner, slot_for
from rvdeals.models import Deal
from rvdeals.scoring import route_matches, score, tier
from rvdeals.state import State

ROOT = Path(__file__).parent.parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
TODAY = date(2026, 11, 22)
NOW = datetime(2026, 11, 22, 7, 5, tzinfo=ZoneInfo("America/Vancouver"))


def deal(**kw):
    base = dict(company="Test", deal_id="T1", origin="Los Angeles", destination="Vancouver", link="https://x.test/d",
                pickup_from=date(2027, 3, 3), pickup_to=date(2027, 3, 8), nights=7, currency="USD",
                nightly_rate=1.0, booking_fee=49.0, included_distance_km=2300, fuel_allowance=300.0, sleeps=4)
    base.update(kw)
    return Deal(**base)


def great(**kw):
    """A genuinely great deal: 10 relaxed nights in May, unlimited km, $300 fuel back."""
    base = dict(pickup_from=date(2027, 5, 10), pickup_to=date(2027, 5, 15), nights=10, included_distance_km=float("inf"))
    base.update(kw)
    return deal(**base)


def test_route_rules():
    assert route_matches(deal(), CFG)
    assert route_matches(deal(origin="Seattle", destination="Denver"), CFG)
    assert route_matches(deal(origin="Toronto / Montreal", destination="Vancouver / Calgary / Edmonton"), CFG)
    assert not route_matches(deal(origin="Denver", destination="Dallas"), CFG)
    assert not route_matches(deal(origin="Calgary", destination="Denver"), CFG)


def test_great_deal_scores_high_and_bad_deal_low():
    good = score(great(), CFG, TODAY)
    assert good.total >= 70 and tier(good.total, CFG) == "now"
    bad = score(deal(nights=2, nightly_rate=59, booking_fee=150, included_distance_km=800,
                     fuel_allowance=0, origin="Denver"), CFG, TODAY)
    assert bad.total < 40 and tier(bad.total, CFG) == "log"
    assert any("cap" in w for w in bad.warnings)


def test_expired_deal_scores_zero():
    assert score(deal(pickup_from=date(2026, 10, 1), pickup_to=date(2026, 10, 5)), CFG, TODAY).total == 0


def test_missing_fields_are_neutral_not_invented():
    s = score(deal(booking_fee=None, included_distance_km=None, fuel_allowance=None, sleeps=None), CFG, TODAY)
    assert 0 < s.total < 100 and "booking fee not listed" in s.warnings


def test_alert_fits_two_segments_plain_ascii():
    d = deal(penalty_terms="A $1,500 no-show fee applies if you do not collect the vehicle on time", bond=2500)
    msg = message.alert(d, score(d, CFG, TODAY), "https://someone.github.io/rv-deal-hunter")
    assert len(msg) <= 300 and msg.isascii() and msg.startswith("RV DEAL ")
    assert "LA > Vancouver" in msg and "/p/T1.html" in msg


def test_digest_fits_and_links_all():
    items = [(deal(deal_id=f"T{i}"), score(deal(), CFG, TODAY)) for i in range(12)]
    msg = message.digest(items, "https://someone.github.io/rv-deal-hunter", TODAY)
    assert len(msg) <= 300 and "more" in msg and msg.endswith("rv-deal-hunter/")


def test_redact_hides_numbers_and_ids():
    out = sms.redact("The 'To' number +1 604 555 0199 is invalid for AC" + "a" * 32)
    assert "604" not in out and "aaaa" not in out


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    return Runner(CFG, State(tmp_path / "s.json"), NOW, fetcher=None, docs=tmp_path / "docs", log=tmp_path / "log")


def test_never_texts_the_same_deal_twice(runner):
    assert runner.handle(great()) == "now"
    runner.state.data["seen"]["T1"]["texted"] = True
    assert runner.state.texts_today(TODAY) == 1
    runner.handle(great())             # seen again (e.g. manual re-run)
    assert runner.state.texts_today(TODAY) == 1


def test_same_route_and_dates_texts_once(runner):
    runner.handle(great(deal_id="A"))
    assert runner.handle(great(deal_id="B")) == "digest"
    assert runner.state.texts_today(TODAY) == 1


def test_hard_cap_of_five_per_day(runner):
    for i in range(8):
        runner.handle(great(deal_id=f"D{i}", pickup_from=date(2027, 5, 1 + i % 20), pickup_to=date(2027, 5, 3 + i % 20)))
    assert runner.state.texts_today(TODAY) == 5
    assert not runner.text("one more", "test")
    assert len(runner.state.data["digest_queue"]) == 3   # over-cap deals are kept, not lost


def test_texts_enabled_false_sends_nothing(runner):
    runner.cfg = {**CFG, "texts_enabled": False}
    runner.handle(great())
    assert runner.state.texts_today(TODAY) == 0


def test_failure_warning_after_three_runs(runner):
    class Boom:
        def get(self, url):
            raise RuntimeError("site down")
    runner.fetcher = Boom()
    runner.cfg = {**CFG, "sources": {"canadream": {"enabled": True}}}
    for day in (1, 2, 3):
        runner.state.data["site_checks"] = {}
        runner.check()
    assert runner.state.data["failures"]["canadream"] == 3
    assert runner.state.data["failure_alerted"]["canadream"] is True
    runner.state.data["site_checks"] = {}
    runner.check()                    # 4th failure: no second warning
    assert runner.state.texts_today(TODAY) == 1


def test_two_checks_per_site_per_day(runner):
    class Empty:
        def get(self, url):
            return (ROOT / "tests/fixtures/fraserway_empty.html").read_text()
    runner.fetcher = Empty()
    runner.cfg = {**CFG, "sources": {"fraserway": {"enabled": True}}}
    runner.check(); runner.check()
    assert runner.check()["fraserway"].startswith("skipped")


def test_slots():
    tz = ZoneInfo("America/Vancouver")
    twice = {**CFG, "schedule": {**CFG["schedule"], "mode": "twice"}}
    assert slot_for(datetime(2026, 7, 1, 7, 40, tzinfo=tz), twice) == "check_am"
    assert slot_for(datetime(2026, 7, 1, 13, 10, tzinfo=tz), twice) == "check_pm"
    assert slot_for(datetime(2026, 7, 1, 18, 5, tzinfo=tz), twice) == "digest"
    assert slot_for(datetime(2026, 7, 1, 3, 0, tzinfo=tz), twice) is None


def test_daily_slot():
    tz = ZoneInfo("America/Vancouver")
    daily = {**CFG, "schedule": {**CFG["schedule"], "mode": "daily"}}
    assert slot_for(datetime(2026, 7, 1, 7, 10, tzinfo=tz), daily) == "daily"
    assert slot_for(datetime(2026, 7, 1, 9, 40, tzinfo=tz), daily) == "daily"   # a late backup run still counts
    assert slot_for(datetime(2026, 7, 1, 6, 50, tzinfo=tz), daily) is None


def test_sunday_checkin_and_season_reminder(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    sunday_feb1 = datetime(2026, 2, 1, 18, 5, tzinfo=ZoneInfo("America/Vancouver"))   # a Sunday
    all_on = {**CFG, "texts": {"weekly_checkin": True, "season_reminders": True}}
    r = Runner(all_on, State(tmp_path / "s.json"), sunday_feb1, None, tmp_path / "d", tmp_path / "l")
    assert r.extras() == ["season reminder sent", "weekly check-in sent"]
    assert r.extras() == []          # not twice


def test_your_settings_send_no_checkin_or_reminder(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    sunday_feb1 = datetime(2026, 2, 1, 18, 5, tzinfo=ZoneInfo("America/Vancouver"))
    r = Runner(CFG, State(tmp_path / "s.json"), sunday_feb1, None, tmp_path / "d", tmp_path / "l")
    assert r.extras() == []


@pytest.mark.parametrize("o,d,nights", [("Los Angeles", "Vancouver", 9), ("Las Vegas", "Seattle", 7),
                                         ("Calgary", "Vancouver", 3), ("Edmonton", "Vancouver", 4),
                                         ("Toronto", "Vancouver", 14), ("Montreal", "Vancouver", 16),
                                         ("Vancouver", "Los Angeles", 7)])
def test_plans_fit_the_nights(o, d, nights):
    opts = plans.options_for(deal(origin=o, destination=d, nights=nights), TODAY)
    assert opts, "no itinerary"
    for op in opts:
        assert len(op.days) == nights
        assert op.days[0].start.lower().startswith(o.lower()[:5]) and op.days[-1].end.lower().startswith(d.lower()[:5])
    assert any(op.fits_hours for op in opts)


def test_plan_page_is_public_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("ALERT_TO", "+16045550199")
    monkeypatch.setenv("TWILIO_API_KEY_SECRET", "supersecretvalue")
    d = deal()
    page = pages.render_plan(d, score(d, CFG, TODAY), TODAY)
    assert "6045550199" not in page and "supersecret" not in page
    assert "check before you go" in page and "Scenic coast" in page and "Fast inland" in page


def test_deal_page_has_answer_steps_tabs_and_maps():
    d = great(booking_fee=None, bond=2500)
    page = pages.render_plan(d, score(d, CFG, TODAY), TODAY, CFG)
    for tab in ("Why this score", "Day by day", "Money", "Fine print"):
        assert f">{tab}</button>" in page
    assert "Great deal" in page and "All-in" in page and "Held on your card" in page
    assert "Grab it in 3 steps" in page and "Book the RV on Test" in page
    assert "google.com/travel/flights" in page and "LAX" in page                # flight there
    assert "google.com/maps/dir/" in page and "Vancouver%2C%20BC" in page     # BC, not Washington
    assert "booking fee</span>" in page                                       # listed under "Not listed"
    assert "<script" in page and "src=" not in page.split("<script")[1]       # no outside scripts


def test_index_has_best_card_and_tabs():
    entries = [{"id": "A", "score": 82, "origin": "LA", "destination": "Vancouver", "last_day": "2026-11-25",
                "allin_low": 500, "allin_high": 660, "leg": "Flight YVR to LAX", "leg_cost": "$160-320"},
               {"id": "B", "score": 55, "origin": "Calgary", "destination": "Vancouver", "last_day": "2027-02-01"}]
    page = pages.render_index(entries, TODAY)
    assert "Best right now" in page and "$500-660</span> all-in" in page
    assert "Great 1" in page and "Good 1" in page and "Closing 1" in page and "All 2" in page and "Skipped 0" in page
    assert 'id="gear"' in page and 'data-pref="camp" data-val="free" data-def="free"' in page
    assert "closes in 3 days" in page


def test_pace_is_judged_against_the_drive():
    sc = score(deal(origin="Calgary", destination="Vancouver", nights=3), CFG, TODAY)
    assert [k for k, t in sc.explain if "nights for a" in t] == ["ok"]          # 970 km in 3 nights: enough
    sc = score(deal(origin="Toronto", destination="Vancouver", nights=5), CFG, TODAY)
    assert [k for k, t in sc.explain if "nights for a" in t] == ["bad"]         # 4,400 km in 5: rushed
    sc = score(deal(origin="Vancouver", destination="Seattle", nights=7), CFG, TODAY)
    assert [k for k, t in sc.explain if "nights for a" in t] == ["good"]



# ---------------- friends ----------------
ME, F1, F2 = "+16045550100", "+17785550101", "+16045550102"


def _people(monkeypatch, friends_value):
    monkeypatch.setenv("ALERT_TO", ME)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC" + "0" * 32)
    monkeypatch.setenv("ALERT_FRIENDS", friends_value)


def test_friend_list_parsing(monkeypatch):
    _people(monkeypatch, f"{F1}, (604) 555-0102 ,  12, {ME}, {F1}")
    people, problems = sms.friends(5)
    assert [n for _, n in people] == [F1, F2]                    # 10-digit number gets +1
    assert len(problems) == 3                                     # invalid, owner duplicate, repeat
    assert not any(ch.isdigit() and "555" in p for p in problems for ch in p)   # no numbers in messages


def test_us_numbers_skipped_unless_allowed(monkeypatch):
    _people(monkeypatch, "+12065550123")                          # 206 = Seattle
    assert sms.friends(5)[0] == [] and "Canadian" in sms.friends(5)[1][0]
    assert len(sms.friends(5, allow_us=True)[0]) == 1


def test_friend_limit(monkeypatch):
    _people(monkeypatch, ",".join(f"+1604555{i:04d}" for i in range(1, 9)))
    people, problems = sms.friends(5)
    assert len(people) == 5 and sum("limit" in p for p in problems) == 3


def test_friends_get_deals_but_not_system_texts(runner, monkeypatch, capsys):
    _people(monkeypatch, f"{F1},{F2}")
    runner.handle(great())                                         # alert: you + 2 friends
    out = capsys.readouterr().out
    assert out.count("would text") == 3 and "friend 2" in out
    assert runner.state.texts_today(TODAY) == 1                    # cap counts messages, not people
    runner.text("site broke", "failure")                         # system: only you
    out = capsys.readouterr().out
    assert out.count("would text") == 1 and "would text you" in out
    assert "555" not in out                                       # numbers never printed


def test_friends_can_be_limited_to_alerts(runner, monkeypatch, capsys):
    _people(monkeypatch, F1)
    runner.cfg = {**CFG, "friends": {**CFG["friends"], "receive": ["alerts"]}}
    runner.text("digest", "digest", "digest")
    assert capsys.readouterr().out.count("would text") == 1


def test_welcome_once_per_friend(runner, monkeypatch):
    _people(monkeypatch, f"{F1},{F2}")
    assert runner.welcome_new_friends() == ["welcomed friend 1", "welcomed friend 2"]
    assert runner.welcome_new_friends() == []
    assert runner.state.texts_today(TODAY) == 0                    # welcomes don't use the cap
    assert not any(F1 in k or "555" in k for k in runner.state.data["welcomed"])   # public file: no numbers
    monkeypatch.setenv("ALERT_FRIENDS", f"{F1},{F2},+16045550103")
    assert runner.welcome_new_friends() == ["welcomed friend 3"]


def test_one_failed_friend_does_not_block_others(runner, monkeypatch, capsys):
    _people(monkeypatch, f"{F1},{F2}")
    sent = []

    def fake_send(body, to, label="you"):
        if to == F1:
            raise sms.SmsError("Twilio error 21610: Attempt to send to unsubscribed recipient")
        sent.append(label)
        return "sent"
    monkeypatch.setattr(sms, "send", fake_send)
    assert runner.text("deal", "alert", "alerts")
    assert sent == ["you", "friend 2"] and "friend 1 failed" in capsys.readouterr().out


# ---------------- getting there and all-in ----------------
from rvdeals import travel  # noqa: E402


def test_flight_there_when_trip_ends_home():
    leg = travel.leg_for(deal(), CFG, TODAY)
    assert leg.direction == "there" and leg.mode == "fly" and "YVR to LAX" in leg.summary
    assert leg.when == date(2027, 3, 3)
    assert (leg.low, leg.high) == (195, 385)          # 160-320 x 1.1 spring break x 1.1 sun season
    assert "spring break" in leg.season
    assert "LAX" in leg.link and "2027-03-03" in leg.link


def test_flight_home_when_trip_starts_home():
    leg = travel.leg_for(deal(origin="Vancouver", destination="Los Angeles"), CFG, TODAY)
    assert leg.direction == "back" and "LAX to YVR" in leg.summary and leg.when == date(2027, 3, 10)


def test_ground_for_seattle_and_none_for_unrelated():
    leg = travel.leg_for(deal(origin="Vancouver", destination="Seattle"), CFG, TODAY)
    assert leg.mode == "ground" and "train" in leg.summary
    assert travel.leg_for(deal(origin="Denver", destination="Dallas"), CFG, TODAY) is None


def test_all_in_adds_up():
    d = deal()
    leg = travel.leg_for(d, CFG, TODAY)
    c = travel.all_in(d, CFG, leg, 2060)
    rv = (1 * 7 + 49) * CFG["scoring"]["usd_to_cad"]
    fuel = max(0, 2060 / 100 * 28 * 1.70 - 300 * CFG["scoring"]["usd_to_cad"])
    assert abs(c.low - (rv + 195 * 2 + fuel + 1 * 35)) < 0.01 and c.complete   # 2 people; mostly free: 1 of 7 paid


def test_alert_has_all_in_and_one_link():
    d = great(bond=2330)
    leg = travel.leg_for(d, CFG, TODAY)
    msg = message.alert(d, score(d, CFG, TODAY), "https://someone.github.io/rv-deal-hunter",
                        travel.all_in(d, CFG, leg, 2060), leg)
    assert len(msg) <= 300 and msg.isascii() and "All-in about" in msg and "flight there" in msg
    assert msg.count("https://") == 1 and "Great" in msg


def test_seasonal_fares():
    f_jan, _ = travel.fare_factor("YYC", date(2027, 1, 20))
    f_jul, n_jul = travel.fare_factor("YYC", date(2027, 7, 15))
    f_xmas, n_xmas = travel.fare_factor("YYC", date(2026, 12, 22))
    assert f_jan < 1 < f_jul < f_xmas and "peak summer" in n_jul and n_xmas == "holidays"
    assert travel.fare_factor("LAX", date(2027, 1, 20))[0] > f_jan                # sun season


def test_summer_costs_more_than_winter():
    summer = travel.all_in(deal(pickup_from=date(2027, 7, 10), pickup_to=date(2027, 7, 12)), CFG, None, 2060)
    winter = travel.all_in(deal(pickup_from=date(2027, 1, 10), pickup_to=date(2027, 1, 12)), CFG, None, 2060)
    assert summer.camping > winter.camping and summer.fuel_gross > winter.fuel_gross


def test_camping_styles():
    c = travel.all_in(deal(), CFG, None, 2060)
    s = c.by_style
    assert s["free"]["low"] < s["mix"]["low"] < s["campgrounds"]["low"]
    assert [s[k]["paid_nights"] for k in ("campgrounds", "mix", "free")] == [7, 4, 1]


def test_every_night_has_sleep_options():
    d = deal(origin="Calgary", destination="Vancouver", nights=6)        # first night: Banff
    page = pages.render_plan(d, score(d, CFG, TODAY), TODAY, CFG)
    assert page.count('class="sleep"') == 6
    assert "BC recreation sites" in page and "Find free spots near" in page
    assert "national parks you must use a campground" in page          # Banff / Lake Louise nights
    assert "Mostly free" in page and "data-cost=" in page and 'data-f="allin"' in page


def test_weak_deals_go_to_skipped_with_a_reason():
    entries = [{"id": "W", "score": 22, "origin": "Seattle", "destination": "New York", "last_day": "2026-12-02",
                "why": "11 nights for a ~4,831 km drive: rushed, long driving days"}]
    page = pages.render_index(entries, TODAY)
    assert "Skipped 1" in page and "All 0" in page and "rushed, long driving days" in page


def test_settings_defaults_match_config():
    assert CFG["costs"]["camping_style"] == "free" and CFG["travel"]["travellers"] == 2
    c = travel.all_in(deal(), CFG, travel.leg_for(deal(), CFG, TODAY), 2060)
    m = c.model(7)
    assert m["dc"] == "free" and m["dp"] == 2 and m["paid"] == {"campgrounds": 7, "mix": 4, "free": 1}
