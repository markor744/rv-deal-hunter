"""A full practice run on the saved test pages: no websites are contacted and no texts are sent.
Output goes to .practice/ (plan pages you can open, and the would-be texts printed below)."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from .sources import canadream, canadream_elmonte, fraserway, imoova
from .state import State

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

URLS = {
    imoova.TABLE_URLS[0]: "imoova_table_usa.html",
    imoova.TABLE_URLS[1]: "imoova_table_canada.html",
    canadream.URL: "canadream_relocation.html",
    canadream_elmonte.ELMONTE_URL: "elmonte_canada_to_us.html",
    canadream_elmonte.CANADREAM_URL: "canadream_canada_to_us.html",
    fraserway.URL: "fraserway_empty.html",
}


class FixtureFetcher:
    requests_made = 0

    def get(self, url: str) -> str:
        if url in URLS:
            return (FIX / URLS[url]).read_text()
        ref = url.rstrip("/").split("/")[-1]
        f = FIX / f"imoova_deal_{ref}.html"
        if f.exists():
            return f.read_text()
        raise FileNotFoundError(f"no saved page for {url} (only some deal pages are saved)")


def run_fixtures(cfg: dict, now: datetime) -> int:
    from . import pages
    from .main import Runner          # late imports: main imports this module
    from .scoring import route_matches
    from .sources import SOURCES

    os.environ["DRY_RUN"] = "1"
    out = ROOT / ".practice"
    shutil.rmtree(out, ignore_errors=True)
    (out / "docs").mkdir(parents=True)
    state = State(out / "state.json")
    r = Runner(cfg, state, now, FixtureFetcher(), docs=out / "docs", log=out / "deals-log.jsonl")
    wanted = lambda d: route_matches(d, cfg)

    report = {}
    for name, module in SOURCES.items():
        try:
            if module is imoova:   # only some deal pages are saved: the rest keep their table facts
                rows = [d for u in imoova.TABLE_URLS for d in imoova.parse_table(r.fetcher.get(u), r.today)]
                deals = [d for d in {d.deal_id: d for d in rows}.values() if wanted(d)]
                for d in deals:
                    try:
                        imoova.enrich(d, r.fetcher.get(d.link), r.today)
                    except FileNotFoundError:
                        d.notes.append("practice run: deal page not saved, table facts only")
            else:
                deals = module.collect(r.fetcher, r.today, wanted, state.seen_ids(), 50)
            tiers = [r.handle(d) for d in deals]
            report[name] = f"{len(deals)} matching deals " + ", ".join(
                f"{t}={tiers.count(t)}" for t in sorted(set(tiers)))
        except Exception as e:
            report[name] = f"FAILED: {type(e).__name__}: {e}"
    pages.write_index(out / "docs", state.data["seen"], r.today, cfg["thresholds"]["digest"],
                      cfg["thresholds"]["text_now"], cfg)
    print(r.digest())
    for k, v in report.items():
        print(f"{k}: {v}")
    print(f"plan pages written to {out / 'docs'}")
    return 0
