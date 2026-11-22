"""RV Deal Hunter command line.

  python -m rvdeals.main scheduled      what GitHub Actions runs: works out the slot from Pacific time
  python -m rvdeals.main check          check the sites now (still max 2 checks per site per day)
  python -m rvdeals.main digest         send the digest now (if anything is waiting)
  python -m rvdeals.main test-sms       send "RV Deal Hunter test message."
  python -m rvdeals.main fixtures       full run on the saved test pages, no websites, no texts
  python -m rvdeals.main status         print a summary (no secrets)
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import message, pages, plans, sms, travel
from .fetch import Fetcher
from .models import Deal, NOT_LISTED
from .scoring import Score, route_matches, score, tier
from .sources import SOURCES
from .state import State

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATE = ROOT / "state" / "state.json"
LOG = ROOT / "state" / "deals-log.jsonl"
CHECKS_PER_SITE_PER_DAY = 2
FAIL_ALERT_AFTER = 3


def load_config(path: Path = ROOT / "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


class Runner:
    def __init__(self, cfg: dict, state: State, now: datetime, fetcher=None, docs: Path = DOCS, log: Path = LOG):
        self.cfg, self.state, self.now = cfg, state, now
        self.today = now.date()
        self.fetcher = fetcher
        self.docs, self.log = Path(docs), Path(log)
        self.cap = cfg["limits"]["max_texts_per_day"]

    # ---------- texting with the hard cap ----------
    def recipients(self, group: str) -> list[tuple[str, str]]:
        """Who gets this kind of text. You get everything; friends get only what config allows.
        group: 'alerts', 'digest', 'season' (can go to friends) or 'system' (only you)."""
        me = sms.owner() or ("(not set)" if sms.dry_run() else None)   # dry runs print, never send
        out = [("you", me)] if me else []
        fcfg = self.cfg.get("friends", {})
        if group != "system" and group in fcfg.get("receive", []):
            people, problems = sms.friends(fcfg.get("max_friends", 5), fcfg.get("us_friends", False))
            for p in problems:
                print(p)
            out += people
        return out

    def text(self, body: str, kind: str, group: str = "system") -> bool:
        """Send one message to everyone it is meant for. The daily cap counts messages, not people."""
        if not self.cfg.get("texts_enabled", True):
            print(f"texts paused (texts_enabled: false); would send {kind}")
            return False
        if not self.state.can_text(self.today, self.cap):
            print(f"daily cap of {self.cap} texts reached; not sending {kind}")
            return False
        people = self.recipients(group)
        if not people:
            print(f"no valid recipient for {kind} (check the ALERT_TO secret)")
            return False
        delivered = 0
        for label, number in people:
            try:
                if sms.send(body, number, label) in ("sent", "dry-run"):
                    delivered += 1
            except sms.SmsError as e:   # one bad number never blocks the others
                print(f"text to {label} failed ({kind}): {e}")
        if delivered:
            self.state.count_text(self.today)
        return delivered > 0

    def welcome_new_friends(self) -> list[str]:
        """One welcome text per new friend, with how to opt out. Not counted in the daily cap,
        but at most max_friends per day, and each friend only once."""
        fcfg = self.cfg.get("friends", {})
        if not self.cfg.get("texts_enabled", True) or not fcfg.get("receive"):
            return []
        people, _ = sms.friends(fcfg.get("max_friends", 5), fcfg.get("us_friends", False))
        done = self.state.data.setdefault("welcomed", {})
        out = []
        for label, number in people:
            fid = sms.friend_id(number)
            if fid in done:
                continue
            try:
                sms.send(fcfg["welcome_text"], number, label)
                done[fid] = self.today.isoformat()
                out.append(f"welcomed {label}")
            except sms.SmsError as e:
                print(f"welcome to {label} failed: {e}")
        return out

    # ---------- deals ----------
    def _log(self, deal: Deal, sc: Score, t: str) -> None:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a") as f:
            f.write(json.dumps({"at": self.now.isoformat(timespec="seconds"), "tier": t, "score": sc.total,
                                "parts": sc.parts, "deal": deal.to_dict()}) + "\n")

    def _remember(self, deal: Deal, sc: Score, t: str, texted: bool) -> None:
        last = deal.pickup_to or deal.pickup_from or (self.today + timedelta(days=30))
        self.state.mark_seen(deal.deal_id, {
            "first_seen": self.today.isoformat(), "score": sc.total, "tier": t, "texted": texted,
            "route": f"{deal.origin} to {deal.destination}", "origin": deal.origin,
            "destination": deal.destination, "company": deal.company, "pickup": deal.pickup_text,
            "when": pages.pickup_line(deal, self.today), "nights": deal.nights, "rate": deal.nightly_rate,
            "currency": deal.currency, "last_day": last.isoformat(), **getattr(self, "_extra", {})})

    def handle(self, deal: Deal) -> str:
        base = self.cfg["plans_base_url"]
        if deal.origin == NOT_LISTED:   # a source posted something we cannot read (Fraserway notice)
            sc = Score(total=self.cfg["thresholds"]["digest"], warnings=deal.notes)
            self.state.data["digest_queue"].append({"notice": f"{deal.company}: new specials posted, "
                                                    f"{deal.booking}. {deal.link}"})
            self._remember(deal, sc, "digest", False)
            self._log(deal, sc, "notice")
            return "notice"
        sc = score(deal, self.cfg, self.today)
        t = tier(sc.total, self.cfg)
        self._log(deal, sc, t)
        leg = travel.leg_for(deal, self.cfg, self.today)
        cost = travel.all_in(deal, self.cfg, leg, sc.route_km)
        self._extra = {"allin_low": cost.low if cost else None, "allin_high": cost.high if cost else None,
                       "leg": leg.summary if leg else None,
                       "leg_cost": travel.range_text(leg.low, leg.high) if leg and leg.high else None,
                       "cost": cost.model(deal.nights) if cost else None,
                       "why": " · ".join(sc.flags[:3]).capitalize()}
        pages.write_plan(self.docs, deal, sc, self.today, self.cfg)     # every matching deal: Skipped shows the weak ones
        texted = False
        twin = f"{deal.company}|{deal.origin}|{deal.destination}|{deal.pickup_from}"
        twins = self.state.data.setdefault("texted_twins", {})
        if t == "now" and twin in twins:   # same route and dates as a deal already texted (other vehicle)
            t = "digest"
        if t == "now" and not self.state.was_texted(deal.deal_id):
            texted = self.text(message.alert(deal, sc, base, cost, leg), f"alert {deal.deal_id}", "alerts")
            if texted:
                twins[twin] = self.today.isoformat()
            else:   # cap reached or paused: keep it for the digest so it is not lost
                t = "digest"
        if t == "digest":
            self.state.data["digest_queue"].append({"id": deal.deal_id, "deal": deal.to_dict(),
                                                    "score": sc.total, **self._extra})
        self._remember(deal, sc, t, texted)
        return t

    def check(self) -> dict:
        report = {}
        seen = self.state.seen_ids()
        wanted = lambda d: route_matches(d, self.cfg)
        max_details = self.cfg["limits"]["max_detail_pages_per_run"]
        for name, module in SOURCES.items():
            if not self.cfg["sources"].get(name, {}).get("enabled", False):
                continue
            if self.state.site_checks_today(self.today, name) >= CHECKS_PER_SITE_PER_DAY:
                report[name] = "skipped: already checked twice today"
                continue
            self.state.count_site_check(self.today, name)
            try:
                deals = module.collect(self.fetcher, self.today, wanted, seen, max_details)
                tiers = [self.handle(d) for d in deals]
                self.state.record_result(name, True)
                report[name] = f"ok: {len(deals)} new matching deals " + (
                    f"({', '.join(f'{t}={tiers.count(t)}' for t in sorted(set(tiers)))})" if tiers else "")
            except Exception as e:
                n = self.state.record_result(name, False)
                report[name] = f"FAILED ({n} in a row): {type(e).__name__}: {e}"
                traceback.print_exc()
                if n >= FAIL_ALERT_AFTER and not self.state.data["failure_alerted"].get(name):
                    if self.text(f"RV Deal Hunter: {name} has failed {n} runs in a row. The site may have "
                                 f"changed. Open the GitHub Actions log to see why.", f"failure {name}"):
                        self.state.data["failure_alerted"][name] = True
        pages.write_index(self.docs, self.state.data["seen"], self.today, self.cfg["thresholds"]["digest"],
                          self.cfg["thresholds"]["text_now"], self.cfg)
        pages.prune_pages(self.docs, self.state.data["seen"], self.today)
        return report

    # ---------- digest, check-ins, reminders ----------
    def digest(self) -> str:
        # Drop deals whose pick-up closed while they waited (e.g. a day the cap was full).
        today = self.today.isoformat()
        q = [x for x in self.state.data["digest_queue"]
             if "notice" in x or (x["deal"].get("pickup_to") or x["deal"].get("pickup_from") or today) >= today]
        self.state.data["digest_queue"] = q
        if not q:
            return "digest: nothing waiting"
        notices = [x["notice"] for x in q if "notice" in x]
        items = []
        for x in q:
            if "deal" in x and not self.state.was_texted(x["id"]):
                d = _deal_from_dict(x["deal"])
                d._allin_low = x.get("allin_low")
                items.append((d, Score(total=x["score"])))
        body = message.digest(items, self.cfg["plans_base_url"], self.today) if items else ""
        if notices:
            body = (body + " " if body else "") + " ".join(notices)
            body = message.ascii_only(body)[:message.MAX_CHARS]
        if self.text(body, "digest", "digest"):
            self.state.data["digest_queue"] = []
            return f"digest sent ({len(items)} deals, {len(notices)} notices)"
        return "digest not sent (kept for tomorrow)"

    def extras(self) -> list[str]:
        """Sunday check-in and season reminders, sent with the 6pm slot."""
        out = []
        d = self.today
        season = {(2, 1): "RV Deal Hunter: spring northbound season starts now. Watch for LA, Vegas and "
                          "Phoenix to Vancouver and Seattle relocations over the next weeks.",
                  (8, 15): "RV Deal Hunter: fall southbound season starts now. Watch for Vancouver, "
                           "Calgary and Seattle relocations heading south."}
        # Each reminder is due on its day or, if that run was missed or the cap was full, the next 3 days.
        for (m, day_), body in season.items():
            due = date(d.year, m, day_)
            key = f"{d.year}-{m:02d}-{day_:02d}"
            if due <= d <= due + timedelta(days=3) and not self.state.data["season_sent"].get(key):
                if self.text(body, "season reminder", "season"):
                    self.state.data["season_sent"][key] = True
                    out.append("season reminder sent")
        # Weekly check-in: Sundays, or the first evening after a Sunday that was missed.
        last = self.state.data.get("last_checkin")
        overdue = last is not None and (d - date.fromisoformat(last)).days >= 7
        if (d.weekday() == 6 or overdue) and last != d.isoformat():
            week = [(d - timedelta(days=i)).isoformat() for i in range(7)]
            texts = sum(self.state.data["texts"].get(x, 0) for x in week)
            failing = [k for k, v in self.state.data["failures"].items() if v]
            body = (f"RV Deal Hunter is still running. Last 7 days: {texts} texts sent. "
                    + (f"Having trouble with: {', '.join(failing)}." if failing else "All sites OK."))
            if self.text(body, "weekly check-in"):
                self.state.data["last_checkin"] = d.isoformat()
                out.append("weekly check-in sent")
        return out


def _deal_from_dict(x: dict) -> Deal:
    from dataclasses import fields
    kw = {}
    for f in fields(Deal):
        v = x.get(f.name)
        if f.name in ("pickup_from", "pickup_to") and v:
            v = date.fromisoformat(v)
        if v == "unlimited":
            v = float("inf")
        if v is not None:
            kw[f.name] = v
    return Deal(**kw)


def slot_for(now: datetime, cfg: dict) -> str | None:
    h = now.hour
    am, pm = cfg["schedule"]["check_hours"]
    dg = cfg["schedule"]["digest_hour"]
    if am <= h < pm:
        return "check_am"
    if pm <= h < dg:
        return "check_pm"
    if dg <= h <= 23:
        return "digest"
    return None


def run_scheduled(runner: "Runner") -> str:
    """What one scheduled GitHub run does. Returns a short log line. The year simulator calls this too."""
    now, state, cfg = runner.now, runner.state, runner.cfg
    slot = slot_for(now, cfg)
    if slot is None or state.slot_done(now.date(), slot):
        return f"nothing to do now ({now:%H:%M} {cfg['schedule']['timezone']}, slot {slot}, already done)"
    state.mark_slot(now.date(), slot)
    if slot == "digest":
        return f"{slot}: {runner.digest()} {runner.extras()}"
    return f"{slot}: {json.dumps(runner.check())}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rvdeals")
    ap.add_argument("command", choices=["scheduled", "check", "digest", "test-sms", "welcome", "fixtures", "simulate", "status"])
    args = ap.parse_args(argv)
    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg["schedule"]["timezone"]))
    state = State(STATE)

    if args.command == "status":
        print(json.dumps({"last_run": state.data["last_run"], "texts_today": state.texts_today(now.date()),
                          "deals_seen": len(state.data["seen"]), "digest_waiting": len(state.data["digest_queue"]),
                          "failures": state.data["failures"], "missing_settings": sms.missing_settings(),
                          "you": "set" if sms.owner() else "missing or invalid",
                          "friends": len(sms.friends(cfg.get("friends", {}).get("max_friends", 5), cfg.get("friends", {}).get("us_friends", False))[0]),
                          "friend_problems": sms.friends(cfg.get("friends", {}).get("max_friends", 5), cfg.get("friends", {}).get("us_friends", False))[1]}, indent=1))
        return 0

    if args.command == "simulate":
        from .simulate import main as simulate_main
        return simulate_main(cfg)

    if args.command == "fixtures":
        from .fixtures_run import run_fixtures
        return run_fixtures(cfg, now)

    runner = Runner(cfg, state, now, Fetcher(cfg["limits"]["seconds_between_requests"]))
    if args.command == "test-sms":
        ok = runner.text("RV Deal Hunter test message.", "test")
        state.save(now)
        print("test text sent" if ok else "test text NOT sent (see message above)")
        return 0 if ok else 1

    print("\n".join(runner.welcome_new_friends()) or "no new friends to welcome")
    if args.command == "welcome":
        state.save(now)
        return 0

    if args.command == "scheduled":
        print(run_scheduled(runner))
    elif args.command == "check":
        print(json.dumps(runner.check(), indent=1))
    elif args.command == "digest":
        print(runner.digest())
    state.save(now)
    print(f"texts sent today: {state.texts_today(now.date())} of {cfg['limits']['max_texts_per_day']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
