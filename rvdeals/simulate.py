"""Year simulator: a time machine for RV Deal Hunter.

Runs the real scheduling, scoring, texting and page code through a whole year of fake days.
Nothing touches the internet and no text is sent: websites are replaced by a deal generator
that follows the real seasons, and the phone is replaced by a recorder.

What it throws at the tool:
  - 6 scheduled runs a day (7:07, 7:37, 13:07, 13:37, 18:07, 18:37 Pacific), each delayed
    0 to 55 minutes and sometimes dropped, like GitHub Actions under load
  - occasional manual "check" runs
  - daylight saving changes and New Year
  - a site outage (4 days) and a one-off site error
  - a friend added in spring, who must get exactly one welcome text
  - spring northbound and fall southbound deal seasons

Then it checks every promise the tool makes and writes a report.

  python -m rvdeals.main simulate            (or: python -m rvdeals.simulate [start-date] [days])
"""
from __future__ import annotations

import copy
import json
import os
import random
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import main as app
from . import message, sms
from .models import Deal
from .scoring import route_matches
from .state import State
from .textutil import parse_day_month, parse_range

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".simulation"
REPORT = ROOT / "reports" / "year-simulation.md"

ME, FRIEND = "+16045550100", "+17785550101"
CRON = [time(7, 7), time(7, 37), time(13, 7), time(13, 37), time(18, 7), time(18, 37)]

# Routes: (origin, destination, season months it's common, weight)
NORTH = {2, 3, 4, 5}
SOUTH = {8, 9, 10, 11}
ROUTES = [
    ("Los Angeles", "Vancouver", NORTH, 3), ("San Francisco", "Seattle", NORTH, 2), ("Las Vegas", "Seattle", NORTH, 2),
    ("Phoenix", "Vancouver", NORTH, 1), ("San Diego", "Vancouver", NORTH, 1), ("Calgary", "Vancouver", NORTH | SOUTH, 2),
    ("Edmonton", "Vancouver", NORTH, 1), ("Toronto", "Vancouver", NORTH, 1), ("Elkhart", "Seattle", NORTH, 1),
    ("Vancouver", "Los Angeles", SOUTH, 3), ("Seattle", "Las Vegas", SOUTH, 2), ("Vancouver", "Calgary", SOUTH, 1),
    ("Seattle", "Phoenix", SOUTH, 1), ("Vancouver", "Seattle", SOUTH, 1),
    ("Denver", "Dallas", set(range(1, 13)), 2), ("Chicago", "Atlanta", set(range(1, 13)), 1),   # not your routes
]


@dataclass
class Sim:
    start: date
    days: int
    seed: int = 7
    texts: list = field(default_factory=list)         # (local datetime, label, kind, body)
    runs: list = field(default_factory=list)          # (local datetime, trigger, result)
    collects: Counter = field(default_factory=Counter)  # (date, source) -> calls
    digests: list = field(default_factory=list)       # (date, [(deal_id, last_day)])
    findings: list = field(default_factory=list)


class SimSource:
    """Stands in for a website. Deals are generated for the whole year up front, so asking twice
    on the same day returns the same deals (like a real site)."""

    def __init__(self, name: str, sim: Sim, rng: random.Random, rate: float, outage=None, blip=None):
        self.name, self.sim, self.outage, self.blip = name, sim, outage or set(), blip or set()
        self.deals: list[Deal] = []
        n = 0
        for k in range(sim.days + 60):
            day = sim.start + timedelta(days=k)
            for o, d, months, weight in ROUTES:
                lam = rate * weight * (1.0 if day.month in months else 0.15)
                if rng.random() < lam:
                    n += 1
                    self.deals.append(_make_deal(rng, name, n, o, d, posted=day))

    def collect(self, fetcher, today, wanted, seen_ids, max_details):
        self.sim.collects[(today, self.name)] += 1
        if today in self.outage or (today, self.sim.collects[(today, self.name)]) in self.blip:
            raise RuntimeError(f"{self.name}: simulated site error")
        live = [d for d in self.deals if d._posted <= today <= (d.pickup_to or d.pickup_from)]
        return [d for d in live if wanted(d) and d.deal_id not in seen_ids][:max_details]


def _make_deal(rng: random.Random, src: str, n: int, o: str, d: str, posted: date) -> Deal:
    lead = rng.choice([1, 3, 5, 8, 14, 21, 30, 45, 60, 90, 130])
    start = posted + timedelta(days=lead)
    window = rng.choice([0, 2, 5, 10, 20])
    usd = o in ("Los Angeles", "San Francisco", "Las Vegas", "Phoenix", "San Diego", "Elkhart", "Seattle",
                "Denver", "Chicago")
    deal = Deal(company=f"Sim {src}", deal_id=f"SIM-{src}-{n}", origin=o, destination=d,
                link=f"https://example.test/{src}/{n}", pickup_from=start, pickup_to=start + timedelta(days=window),
                pickup_text=f"{start:%d %b} - {start + timedelta(days=window):%d %b}",
                nights=rng.choice([3, 4, 5, 6, 7, 8, 10, 12]), extra_nights=rng.choice([None, 2, 5]),
                currency="USD" if usd else "CAD", nightly_rate=rng.choice([1, 1, 1, 1, 5, 19, 39, 49]),
                booking_fee=rng.choice([None, 0, 49, 99]), bond=rng.choice([None, 1000, 2330, 5000]),
                included_distance_km=rng.choice([None, float("inf"), 800, 1500, 2200, 3000, 5000]),
                fuel_allowance=rng.choice([None, 0, 0, 100, 150, 300]), sleeps=rng.choice([None, 2, 4, 6]),
                vehicle="Simulated motorhome")
    deal._posted = posted
    return deal


def _record_sends(sim: Sim, clock: dict):
    def fake_send(body, to, label="you"):
        sim.texts.append((clock["now"], label, clock.get("kind", "?"), body))
        return "sent"
    return fake_send


def run(start: date, days: int, cfg: dict, seed: int = 7) -> Sim:
    tz = ZoneInfo(cfg["schedule"]["timezone"])
    sim = Sim(start, days, seed)
    rng = random.Random(seed)
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "docs").mkdir(parents=True)

    # A 4-day outage two-thirds of the way in, and a one-off error early on.
    outage_start = start + timedelta(days=int(days * 0.6))
    sources = {
        "imoova": SimSource("imoova", sim, random.Random(seed + 1), 0.05),
        "canadream": SimSource("canadream", sim, random.Random(seed + 2), 0.02,
                               outage={outage_start + timedelta(days=i) for i in range(4)}),
        "fraserway": SimSource("fraserway", sim, random.Random(seed + 3), 0.01,
                               blip={(start + timedelta(days=20), 1)}),
    }
    sim.outage = (outage_start, outage_start + timedelta(days=3))

    # Hard scenarios on fixed dates (used when they fall inside the simulated range):
    #  - GitHub drops BOTH 6pm runs on Feb 1 (spring reminder day) and on the DST Sunday in March
    #  - a burst of 9 great deals on the Sunday in May, more than the daily cap allows
    def nth_sunday(y, m, n):
        d0 = date(y, m, 1)
        return d0 + timedelta(days=(6 - d0.weekday()) % 7 + 7 * (n - 1))
    years = {start.year, start.year + 1}
    sim.forced_drops = {(date(y, 2, 1), "digest") for y in years} | {(nth_sunday(y, 3, 2), "digest") for y in years}
    sim.dst_days = {nth_sunday(y, 3, 2) for y in years} | {nth_sunday(y, 11, 1) for y in years}
    burst = nth_sunday(start.year + 1, 5, 2)
    sim.burst_day = burst
    brng = random.Random(seed + 9)
    for i in range(9):
        d = _make_deal(brng, "imoova", 90000 + i, "Los Angeles", "Vancouver", posted=burst)
        d.nightly_rate, d.booking_fee, d.nights, d.fuel_allowance = 1, 0, 10, 300
        d.included_distance_km, d.sleeps = float("inf"), 4
        d.pickup_from = burst + timedelta(days=14 + i)
        d.pickup_to = d.pickup_from + timedelta(days=1)       # closes fast: tests the digest's expiry filter
        sources["imoova"].deals.append(d)
    cfg = {**cfg, "sources": {k: {"enabled": True} for k in sources}}

    # Swap the outside world for recorders.
    clock = {}
    saved = (app.SOURCES, sms.send, app.Runner.text, message.digest)
    app.SOURCES = sources
    sms.send = _record_sends(sim, clock)
    orig_text, orig_digest = app.Runner.text, message.digest

    def text(self, body, kind, group="system"):
        clock["kind"] = kind
        return orig_text(self, body, kind, group)

    def digest(items, base, today=None, **kw):
        sim.digests.append((today, [(d.deal_id, d.pickup_to or d.pickup_from) for d, _ in items]))
        return orig_digest(items, base, today, **kw)
    app.Runner.text, message.digest = text, digest
    env_before = {k: os.environ.get(k) for k in ("ALERT_TO", "ALERT_FRIENDS", "TWILIO_ACCOUNT_SID", "DRY_RUN")}
    os.environ.update({"ALERT_TO": ME, "TWILIO_ACCOUNT_SID": "AC" + "0" * 32, "ALERT_FRIENDS": ""})
    os.environ.pop("DRY_RUN", None)
    friend_day = start + timedelta(days=int(days * 0.3))
    sim.friend_day = friend_day

    state_path = OUT / "state.json"
    log = open(OUT / "run-log.txt", "w")
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = log
    try:
        for k in range(days):
            day = start + timedelta(days=k)
            if day >= friend_day:
                os.environ["ALERT_FRIENDS"] = FRIEND
            events = []
            for c in CRON:
                if rng.random() < 0.08:          # GitHub dropped this run
                    continue
                if (day, "digest") in sim.forced_drops and c.hour == 18:
                    continue
                at = datetime.combine(day, c, tz) + timedelta(minutes=rng.randint(0, 55))
                events.append((at, "scheduled"))
            if rng.random() < 0.04:              # you pressed "Run workflow" (check)
                events.append((datetime.combine(day, time(rng.randint(9, 21), 30), tz), "check"))
            for at, trigger in sorted(events):
                at = at.astimezone(tz)            # normalizes the DST gap/overlap
                clock["now"] = at
                state = State(state_path)
                r = app.Runner(cfg, state, at, fetcher=None, docs=OUT / "docs", log=OUT / "deals-log.jsonl")
                clock["kind"] = "welcome"
                r.welcome_new_friends()
                result = app.run_scheduled(r) if trigger == "scheduled" else f"manual: {json.dumps(r.check())}"
                state.save(at)
                sim.runs.append((at, trigger, result))
    finally:
        sys.stdout, sys.stderr = real_out, real_err
        log.close()
        app.SOURCES, sms.send, app.Runner.text, message.digest = saved
        for k, v in env_before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    sim.sources = sources
    sim.final_state = json.loads(state_path.read_text())
    return sim


# ------------------------------------------------------------------ checks

def check(sim: Sim, cfg: dict) -> list[tuple[str, bool, str]]:
    cap = cfg["limits"]["max_texts_per_day"]
    res = []
    mine = [t for t in sim.texts if t[1] == "you"]
    per_day = Counter(t[0].date() for t in mine if t[2] != "welcome")
    worst = max(per_day.values() or [0])
    res.append(("Never more than %d texts a day" % cap, worst <= cap, f"busiest day: {worst}"))

    alerts = [t for t in mine if t[2].startswith("alert ")]
    ids = Counter(t[2].split(" ", 1)[1] for t in alerts)
    dup = [i for i, c in ids.items() if c > 1]
    res.append(("No deal is texted twice", not dup, f"{len(ids)} deals alerted, repeats: {dup[:3]}"))

    long_ = [t[3] for t in sim.texts if len(t[3]) > 300 or not t[3].isascii()]
    res.append(("Every text is plain and 300 characters or less", not long_, f"{len(sim.texts)} texts checked"))

    by_site_day = [c for (d, s), c in sim.collects.items() if c > 2]
    res.append(("Each site is checked at most twice a day", not by_site_day,
                f"max per site per day: {max(sim.collects.values() or [0])}"))

    slots = defaultdict(set)
    for at, trig, result in sim.runs:
        if trig == "scheduled" and not result.startswith("nothing"):
            slots[at.date()].add(result.split(":", 1)[0])
    all_days = [sim.start + timedelta(days=k) for k in range(sim.days)]
    double = [d for d in all_days if sum(1 for at, trig, r in sim.runs
                                          if at.date() == d and trig == "scheduled" and r.startswith("digest")) > 1]
    res.append(("Each slot (7am, 1pm, 6pm) runs at most once a day", not double, f"days with a repeat: {len(double)}"))
    missed = {s: sum(1 for d in all_days if s not in slots[d]) for s in ("check_am", "check_pm", "digest")}
    res.append(("Slots are rarely missed even when GitHub drops runs", sum(missed.values()) <= sim.days * 0.05,
                f"missed: {missed} (both runs of a slot dropped or delayed out)"))

    sundays = [d for d in all_days if d.weekday() == 6]
    checkins = {t[0].date() for t in mine if t[2] == "weekly check-in"}
    weeks_without = [s for s in sundays if not any(s <= c < s + timedelta(days=7) for c in checkins)]
    res.append(("A 'still running' text arrives every week", not weeks_without,
                f"{len(checkins)} check-ins for {len(sundays)} weeks; weeks with none: {[str(x) for x in weeks_without[:4]]}"))

    for m, d_, name in ((2, 1, "spring"), (8, 15, "fall")):
        target = [x for x in all_days if (x.month, x.day) == (m, d_)]
        if not target:
            continue
        got = [t for t in mine if t[2] == "season reminder" and name in t[3].lower()]
        res.append((f"The {name} season reminder arrives once, on or just after {target[0]:%b %d}",
                    len(got) == 1 and target[0] <= got[0][0].date() <= target[0] + timedelta(days=3),
                    f"sent: {[str(g[0].date()) for g in got]}"))

    dst = sorted(d for d in sim.dst_days if sim.start <= d < sim.start + timedelta(days=sim.days))
    dst_missed = [str(d) for d in dst if len(slots[d] - {"digest"}) < 2 and (d, "digest") not in sim.forced_drops]
    res.append(("Daylight saving days still run the 7am and 1pm checks", not dst_missed,
                f"DST days {[str(d) for d in dst]}, missed: {dst_missed}"))

    if sim.start <= sim.burst_day < sim.start + timedelta(days=sim.days):
        b = sim.burst_day
        burst_texts = per_day.get(b, 0)
        burst_ids = {f"SIM-imoova-{90000 + i}" for i in range(9)}
        reached = {t[2].split(" ", 1)[1] for t in alerts} | {i for _, items in sim.digests for i, _ in items}
        res.append(("A burst of 9 great deals respects the cap and still reaches you",
                    burst_texts <= cap and burst_ids <= reached | {i for i in burst_ids if seen_twin(sim, i)},
                    f"{burst_texts} texts that day; {len(burst_ids & reached)} of 9 reached you directly"))
        wk = [c for c in {t[0].date() for t in mine if t[2] == "weekly check-in"} if b <= c < b + timedelta(days=7)]
        res.append(("The weekly check-in still comes the week of the burst", bool(wk), f"sent: {[str(x) for x in wk]}"))

    fails = [t for t in mine if t[2].startswith("failure")]
    cd = [t for t in fails if "canadream" in t[2]]
    res.append(("A 4-day site outage gives exactly one warning text", len(cd) == 1,
                f"warnings: {[(str(t[0].date()), t[2]) for t in fails]}"))
    res.append(("A one-off site error gives no warning", not any("fraserway" in t[2] for t in fails), ""))

    friend_texts = [t for t in sim.texts if t[1] == "friend 1"]
    welcomes = [t for t in friend_texts if t[2] == "welcome"]
    sys_to_friend = [t for t in friend_texts if t[2].startswith(("failure", "weekly", "test"))]
    early = [t for t in friend_texts if t[0].date() < sim.friend_day]
    res.append(("A new friend gets exactly one welcome text", len(welcomes) == 1, f"welcomes: {len(welcomes)}"))
    res.append(("Friends never get system texts, or texts from before they were added",
                not sys_to_friend and not early, f"friend got {len(friend_texts)} texts"))

    stale = [(d, i, last) for d, items in sim.digests for i, last in items if last and d and last < d]
    res.append(("The digest never lists a deal whose pick-up has closed", not stale,
                f"stale entries: {len(stale)}, e.g. {[(str(a), b, str(c)) for a, b, c in stale[:2]]}"))

    # Every great deal reaches you: texted, or in a digest, or a twin of one that was texted.
    seen = sim.final_state["seen"]
    great = [k for k, v in seen.items() if v.get("score", 0) >= cfg["thresholds"]["text_now"]]
    in_digest = {i for _, items in sim.digests for i, _ in items}
    lost = [k for k in great if not seen[k].get("texted") and k not in in_digest]
    res.append(("No great deal is lost (texted, or in a digest)", not lost, f"{len(great)} great deals, lost: {lost[:3]}"))

    size = (OUT / "state.json").stat().st_size
    pages_ = len(list((OUT / "docs" / "p").glob("*.html")))
    live = sum(1 for v in seen.values() if v.get("last_day", "0") >= (sim.start + timedelta(days=sim.days - 1)).isoformat())
    logsize = (OUT / "deals-log.jsonl").stat().st_size if (OUT / "deals-log.jsonl").exists() else 0
    res.append(("Memory file stays small after a year", size < 400_000, f"{size / 1000:.0f} KB"))
    res.append(("Old plan pages are cleaned up", pages_ <= live + 200, f"{pages_} pages on disk, {live} deals still open"))
    res.append(("Deal log stays a reasonable size", logsize < 3_000_000, f"{logsize / 1e6:.1f} MB"))

    # Dates without a year ('23 Nov - 2 Dec') read correctly on every day of the year.
    bad = []
    for k in range(366):
        today = date(2027, 1, 1) + timedelta(days=k)
        for ahead in (0, 10, 40, 100, 200):
            a = today + timedelta(days=ahead)
            for span in (0, 5, 25):
                b = a + timedelta(days=span)
                got = parse_range(f"{a.day} {a:%b} - {b.day} {b:%b}", today)
                if got != (a, b):
                    bad.append((str(today), f"{a.day} {a:%b} - {b.day} {b:%b}", [str(x) for x in got]))
            if parse_day_month(f"{a.day} {a:%b}", today) != a:
                bad.append((str(today), f"{a.day} {a:%b}", "single date"))
    res.append(("Dates without a year are read right on every day of the year", not bad,
                f"{len(bad)} wrong, e.g. {bad[:2]}"))

    # Scores spread out: a good score means something only if bad deals score low.
    import statistics
    scores = [v.get("score", 0) for v in seen.values()]
    if len(scores) > 20:
        sd = statistics.pstdev(scores)
        band = sum(1 for s in scores if 60 <= s < 76) / len(scores)
        res.append(("Scores spread out instead of bunching around one number", sd >= 12 and band <= 0.4,
                    f"{len(scores)} matching deals, spread (std dev) {sd:.0f}, {band:.0%} between 60 and 75, "
                    f"range {min(scores)}-{max(scores)}"))

    # Seasonal content follows the calendar.
    from . import pages
    from .scoring import score
    from .travel import all_in, leg_for

    def page_for(o, dst, when):
        d = Deal(company="Sim", deal_id="X", origin=o, destination=dst, link="https://example.test",
                 pickup_from=when, pickup_to=when + timedelta(days=3), nights=6, nightly_rate=1, booking_fee=49,
                 currency="CAD", fuel_allowance=0, sleeps=4)
        return d, pages.render_plan(d, score(d, cfg, when - timedelta(days=20)), when - timedelta(days=20), cfg)
    _, jan = page_for("Calgary", "Vancouver", date(2027, 1, 15))
    _, jul = page_for("Calgary", "Vancouver", date(2027, 7, 15))
    res.append(("Winter road warnings show in January and not in July",
                "winter tire" in jan and "winter tire" not in jul and "Wildfire" in jul and "Wildfire" not in jan, ""))
    costs = {}
    for m in (1, 3, 7, 12):
        d, _ = page_for("Los Angeles", "Vancouver", date(2027, m, 10))
        lg = leg_for(d, cfg, date(2027, m, 10) - timedelta(days=30))
        costs[m] = all_in(d, cfg, lg, 2060).low
    res.append(("Trips cost more in summer and holidays than in January",
                costs[1] < costs[3] < costs[7] and costs[1] < costs[12], {k: round(v) for k, v in costs.items()}))
    return res


def seen_twin(sim: Sim, deal_id: str) -> bool:
    """True if the deal shares route and dates with one that was texted (we text one of a set)."""
    return sim.final_state["seen"].get(deal_id, {}).get("tier") == "digest"


def report(sim: Sim, results, cfg: dict) -> str:
    months = defaultdict(Counter)
    for at, label, kind, body in sim.texts:
        if label != "you":
            continue
        k = kind.split(" ")[0]
        k = "alert" if k == "daily" else k     # a daily text with several great deals counts as alerts
        months[(at.year, at.month)][k] += 1
    for at, trig, r in sim.runs:
        months[(at.year, at.month)]["runs"] += 1
    seen = sim.final_state["seen"]
    found = Counter()
    for v in seen.values():
        d = date.fromisoformat(v["first_seen"])
        found[(d.year, d.month)] += 1
    ok = sum(1 for _, p, _ in results if p)
    lines = [f"# RV Deal Hunter: year simulation",
             f"", f"Simulated {sim.start} to {sim.start + timedelta(days=sim.days - 1)} ({sim.days} days), "
             f"{len(sim.runs)} runs, {len(sim.texts)} texts recorded (none sent). "
             f"**{ok} of {len(results)} checks passed.**", "",
             "## Checks", "", "| | Check | Detail |", "|---|---|---|"]
    lines += [f"| {'PASS' if p else '**FAIL**'} | {name} | {detail} |" for name, p, detail in results]
    lines += ["", "## Month by month (texts to you)", "",
              "| Month | New matching deals | Alerts | Digests | Check-ins | Reminders | Warnings | Runs |",
              "|---|---|---|---|---|---|---|---|"]
    for key in sorted(months):
        c = months[key]
        lines.append(f"| {date(key[0], key[1], 1):%b %Y} | {found[key]} | {c['alert']} | {c['digest']} | "
                     f"{c['weekly']} | {c['season']} | {c['failure']} | {c['runs']} |")
    ex = [t for t in sim.texts if t[1] == "you" and t[2].startswith("alert")][:2]
    ex += [t for t in sim.texts if t[1] == "you" and t[2] == "digest"][:1]
    lines += ["", "## Sample texts", ""] + [f"- {t[0]:%b %d %H:%M}: `{t[3]}`" for t in ex]
    return "\n".join(lines) + "\n"


def all_texts_on(cfg: dict) -> dict:
    """A copy of the settings with every kind of text switched on, so every promise gets tested."""
    c = copy.deepcopy(cfg)
    c["texts"] = {k: True for k in ("good_deals_digest", "weekly_checkin", "season_reminders", "site_warnings")}
    c["schedule"] = {**c["schedule"], "mode": "twice"}
    return c


def check_your_settings(sim: Sim, cfg: dict) -> list[tuple[str, bool, str]]:
    """Checks for a year run with the real config.yaml switches."""
    sw = cfg.get("texts") or {}
    mine = [t for t in sim.texts if t[1] == "you"]
    kinds = Counter(t[2].split(" ")[0] for t in mine)
    res = []
    if not sw.get("weekly_checkin", True):
        res.append(("Your settings: no Sunday check-in texts", kinds["weekly"] == 0, f"check-ins: {kinds['weekly']}"))
    if not sw.get("season_reminders", True):
        res.append(("Your settings: no season reminder texts", kinds["season"] == 0, f"reminders: {kinds['season']}"))
    if not sw.get("good_deals_digest", True):
        seen = sim.final_state["seen"]
        weak = [i for _, items in sim.digests for i, _ in items
                if seen.get(i, {}).get("score", 0) < cfg["thresholds"]["text_now"]]
        res.append(("Your settings: multi-deal texts only carry great deals", not weak,
                    f"{len(sim.digests)} digests, non-great entries: {len(weak)}"))
    great = [k for k, v in sim.final_state["seen"].items() if v.get("score", 0) >= cfg["thresholds"]["text_now"]]
    in_digest = {i for _, items in sim.digests for i, _ in items}
    # A twin (another vehicle, same company, route and dates as a deal already texted) is not lost.
    lost = [k for k in great if not sim.final_state["seen"][k].get("texted") and k not in in_digest
            and not sim.final_state["seen"][k].get("twin_of_texted")]
    res.append(("Your settings: no great deal is lost", not lost, f"{len(great)} great deals, lost: {lost[:3]}"))
    days = {t[0].date() for t in mine}
    if cfg["schedule"].get("mode") == "daily":
        deal_texts = Counter(t[0].date() for t in mine if t[2].split(" ")[0] in ("alert", "daily", "digest"))
        res.append(("Your settings: at most one deal text a day", max(deal_texts.values() or [0]) <= 1,
                    f"busiest day: {max(deal_texts.values() or [0])} deal texts"))
        great_days = {date.fromisoformat(v["first_seen"]) for v in sim.final_state["seen"].values()
                      if v.get("score", 0) >= cfg["thresholds"]["text_now"]}
        quiet = [d for d in deal_texts if d not in great_days]
        res.append(("Your settings: no deal text on a day without a new great deal", not quiet,
                    f"{len(deal_texts)} days with a deal text, {len(great_days)} days with a new great deal"))
        ids = Counter(i for t in mine if t[2].startswith("alert ") for i in [t[2].split(" ", 1)[1]])
        res.append(("Your settings: no deal is texted twice", all(c == 1 for c in ids.values()), f"{len(ids)} single alerts"))
    other = {k: v for k, v in kinds.items() if k not in ("alert", "daily", "digest", "failure")}
    res.append(("Your settings: every text is about a deal (or a broken site)", not other,
                f"texts on {len(days)} of {sim.days} days; {dict(kinds)}"))
    return res


def main(cfg: dict | None = None, start: date | None = None, days: int = 365, seed: int = 7) -> int:
    cfg = cfg or app.load_config()
    start = start or date.today()
    full = all_texts_on(cfg)
    sim = run(start, days, full, seed)            # every kind of text on: tests every promise
    results = check(sim, full)
    yours = run(start, days, cfg, seed)           # the real config.yaml: what you would get
    results += check_your_settings(yours, cfg)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(report(yours, results, cfg))
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  ({detail})")
    print(f"report: {REPORT}")
    return 0 if all(p for _, p, _ in results) else 1


if __name__ == "__main__":
    s = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    sys.exit(main(start=s, days=n, seed=sd))
