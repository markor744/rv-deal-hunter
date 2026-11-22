"""The tool's memory, kept in state/state.json and committed back to the repo after each run.

It holds only public deal facts (IDs, routes, scores) and counters. Never personal data.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

EMPTY = {"seen": {}, "texts": {}, "slots_done": {}, "site_checks": {}, "digest_queue": [],
         "failures": {}, "failure_alerted": {}, "texted_twins": {}, "welcomed": {}, "season_sent": {}, "last_checkin": None, "last_run": None}


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.data = {**json.loads(json.dumps(EMPTY)), **data}

    # ---- texts and the hard daily cap ----
    def texts_today(self, today: date) -> int:
        return self.data["texts"].get(today.isoformat(), 0)

    def can_text(self, today: date, cap: int) -> bool:
        return self.texts_today(today) < cap

    def count_text(self, today: date) -> None:
        k = today.isoformat()
        self.data["texts"][k] = self.data["texts"].get(k, 0) + 1

    # ---- deals ----
    def seen_ids(self) -> set[str]:
        return set(self.data["seen"])

    def mark_seen(self, deal_id: str, info: dict) -> None:
        self.data["seen"][deal_id] = info

    def was_texted(self, deal_id: str) -> bool:
        return bool(self.data["seen"].get(deal_id, {}).get("texted"))

    # ---- schedule slots (so a late or doubled scheduled run never repeats a check) ----
    def slot_done(self, today: date, slot: str) -> bool:
        return slot in self.data["slots_done"].get(today.isoformat(), [])

    def mark_slot(self, today: date, slot: str) -> None:
        self.data["slots_done"].setdefault(today.isoformat(), []).append(slot)

    def site_checks_today(self, today: date, source: str) -> int:
        return self.data["site_checks"].get(today.isoformat(), {}).get(source, 0)

    def count_site_check(self, today: date, source: str) -> None:
        day = self.data["site_checks"].setdefault(today.isoformat(), {})
        day[source] = day.get(source, 0) + 1

    # ---- failures ----
    def record_result(self, source: str, ok: bool) -> int:
        f = self.data["failures"]
        f[source] = 0 if ok else f.get(source, 0) + 1
        if ok:
            self.data["failure_alerted"][source] = False
        return f[source]

    def save(self, now: datetime) -> None:
        self.data["last_run"] = now.isoformat(timespec="seconds")
        cutoff = (now.date() - timedelta(days=30)).isoformat()
        for k in ("texts", "slots_done", "site_checks"):
            self.data[k] = {d: v for d, v in self.data[k].items() if d >= cutoff}
        self.data["texted_twins"] = {k: v for k, v in self.data["texted_twins"].items() if v >= cutoff}
        old = (now.date() - timedelta(days=400)).isoformat()
        self.data["seen"] = {k: v for k, v in self.data["seen"].items() if v.get("first_seen", "9") >= old}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True) + "\n")
