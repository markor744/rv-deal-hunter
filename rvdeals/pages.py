"""The public web pages (GitHub Pages, docs/): one page per deal plus the deals list.

Phone first. A deal page answers, in this order: is it worth it, what will I pay, when must I
pick up, then tabs for Overview, Itinerary, Costs and Fine print. Only deal facts appear here,
never personal data. No outside scripts, fonts or trackers.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

from .itinerary_data import MAPS
from .models import Deal, NOT_LISTED
from .plans import KMH, MAX_HOURS, options_for
from .geo import split_places
from .scoring import Score
from .travel import CAMPING_STYLES, all_in, leg_for, money, range_text
from .itinerary_data import FREE_TIP, free_options

DEFAULT_CFG = {"scoring": {"usd_to_cad": 1.38}}

CHECK = "check before you go"
CANADA = {"vancouver", "abbotsford", "victoria", "calgary", "edmonton", "toronto", "montreal",
          "halifax", "kamloops", "kelowna", "whitehorse", "nanaimo", "penticton", "white rock"}

# ------------------------------------------------------------------ small helpers

def _e(s) -> str:
    return html.escape(str(s))


def _sym(cur: str) -> str:
    if cur == "USD":
        return "US$"
    if cur.startswith("CAD"):
        return "CA$"
    return "$"


def _m(v: float | None, cur: str, cents: bool = False) -> str:
    if v is None:
        return NOT_LISTED
    if cents or (v != int(v) and v < 100):
        return f"{_sym(cur)}{v:,.2f}"
    return f"{_sym(cur)}{v:,.0f}"


def _d(x: date | None) -> str:
    return f"{x:%b} {x.day}" if x else NOT_LISTED


def _days_left(deal: Deal, today: date) -> int | None:
    last = deal.pickup_to or deal.pickup_from
    return (last - today).days if last else None


def verdict(total: int) -> tuple[str, str]:
    if total >= 70:
        return "Great deal", "great"
    if total >= 40:
        return "Worth a look", "ok"
    return "Weak deal", "weak"


def estimate(deal: Deal) -> tuple[float | None, bool]:
    """What you pay up front for the relocation nights + booking fee. (amount, all parts known)."""
    if deal.nightly_rate is None or not deal.nights:
        return None, False
    return deal.nightly_rate * deal.nights + (deal.booking_fee or 0), deal.booking_fee is not None


def pickup_line(deal: Deal, today: date) -> str:
    a, b = deal.pickup_from, deal.pickup_to
    if a and b and a < today:
        return f"Pick up by {_d(b)}"
    if a and b:
        return f"Pick up {_d(a)} to {_d(b)}"
    if a:
        return f"Pick up from {_d(a)}"
    return "Pick-up dates not listed"


def _place(key: str, fallback: str) -> str:
    return MAPS.get(key, fallback.split("/")[0].split("(")[0].strip())


def maps_route(keys_names: list[tuple[str, str]]) -> str:
    pts = [_place(k, n) for k, n in keys_names]
    mid = pts[1:-1]
    if len(mid) > 8:   # Google Maps links take a limited number of stops: keep an even spread
        step = len(mid) / 8
        mid = [mid[int(i * step)] for i in range(8)]
    q = {"api": "1", "origin": pts[0], "destination": pts[-1], "travelmode": "driving"}
    if mid:
        q["waypoints"] = "|".join(mid)
    return "https://www.google.com/maps/dir/?" + urlencode(q, quote_via=quote)


def maps_search(q: str) -> str:
    return "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": q}, quote_via=quote)


# ------------------------------------------------------------------ "why this score"

def reasons(deal: Deal, sc: Score | None, today: date) -> list[tuple[str, str]]:
    """(rating, text) with rating good / ok / bad / unknown."""
    if sc is not None and sc.explain:      # the score's own reasons, so page and number always agree
        return list(sc.explain)
    out = []
    n = deal.nights
    if n is None:
        out.append(("unknown", "Number of nights not listed"))
    else:
        extra = f", plus up to {deal.extra_nights} more at {_m(deal.extra_night_rate, deal.currency)}/night" \
            if deal.extra_nights else ""
        rkm0 = sc.route_km if sc else None
        need = (rkm0 / (KMH * MAX_HOURS)) if rkm0 else None   # nights needed for days under 5 h
        if need and n < need * 0.85:
            rating, why = "bad", f" (tight for a ~{rkm0:,.0f} km drive)"
        elif n >= 7 or (need and n >= need * 1.5):
            rating, why = "good", ""
        else:
            rating, why = "ok", ""
        out.append((rating, f"{n} nights at the relocation rate{extra}{why}"))

    cpn = sc.real_cost_per_night_cad if sc else None
    if cpn is None:
        out.append(("unknown", "Nightly price not listed"))
    else:
        fee = "" if deal.booking_fee is not None else " (booking fee not listed)"
        out.append(("good" if cpn <= 15 else "ok" if cpn <= 35 else "bad",
                    f"About CA${cpn:,.0f} a night with the fee included{fee}"))

    cap, rkm = deal.included_distance_km, sc.route_km if sc else None
    if cap == float("inf"):
        out.append(("good", "Unlimited distance"))
    elif cap is None:
        out.append(("unknown", "Distance allowance not listed"))
    elif rkm:
        r = cap / rkm
        out.append(("good" if r >= 1.15 else "ok" if r >= 1 else "bad",
                    f"{cap:,.0f} km included for a ~{rkm:,.0f} km drive"
                    + ("" if r >= 1 else ": you'd pay for the extra")))
    else:
        out.append(("ok", f"{cap:,.0f} km included"))

    if deal.fuel_allowance is None:
        out.append(("unknown", "Fuel allowance not listed"))
    elif deal.fuel_allowance == 0:
        out.append(("bad", "No fuel allowance"))
    else:
        out.append(("good" if deal.fuel_allowance >= 200 else "ok",
                    f"{_m(deal.fuel_allowance, deal.currency)} back for fuel"))

    left = _days_left(deal, today)
    start = (deal.pickup_from - today).days if deal.pickup_from else None
    if left is None:
        out.append(("unknown", "Pick-up dates not listed"))
    elif left < 0:
        out.append(("bad", "Pick-up window has passed"))
    elif left <= 7:
        out.append(("ok", f"Pick-up window closes in {left} day{'s' if left != 1 else ''}"))
    elif start is not None and start > 120:
        out.append(("ok", f"Pick-up is {start} days away"))
    else:
        out.append(("good", f"Pick-up window is open for {left} more days"))

    if deal.sleeps is None:
        out.append(("unknown", "Sleeping capacity not listed"))
    else:
        out.append(("good" if deal.sleeps >= 2 else "bad", f"Sleeps {deal.sleeps}"))
    if sc and sc.parts.get("priority_origin"):
        out.append(("good", "Starts in one of your priority cities"))
    order = {"bad": 0, "ok": 1, "good": 2, "unknown": 3}
    return sorted(out, key=lambda r: order[r[0]])


# ------------------------------------------------------------------ styles and script

CSS = """
:root{--bg:#f4f2ec;--surface:#fff;--ink:#1b1b19;--mute:#6b6860;--line:#e4e0d6;--accent:#1d6b57;--accent-ink:#fff;
--great:#1d7a4f;--ok:#a86a00;--weak:#8a8780;--bad:#b3412e;--soft:#eef5f1;--warnbg:#fdf3e1;--warn:#7f5200;--r:14px}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--surface:#1c1c1a;--ink:#edece7;--mute:#a3a097;--line:#302f2c;
--accent:#5fc6a5;--accent-ink:#0b1d17;--great:#5fc6a5;--ok:#e7b04f;--weak:#8f8c84;--bad:#ef8a75;--soft:#16241f;--warnbg:#2a2215;--warn:#f0c27a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121211;--surface:#1c1c1a;--ink:#edece7;--mute:#a3a097;--line:#302f2c;
--accent:#5fc6a5;--accent-ink:#0b1d17;--great:#5fc6a5;--ok:#e7b04f;--weak:#8f8c84;--bad:#ef8a75;--soft:#16241f;--warnbg:#2a2215;--warn:#f0c27a;color-scheme:dark}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}main{max-width:680px;margin:0 auto;padding-block:0 40px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.top{display:flex;justify-content:space-between;align-items:center;padding:14px 0 6px;font-size:.9rem;color:var(--mute)}
.top a{text-decoration:none;font-weight:600}
h1{font-size:1.65rem;line-height:1.2;margin:6px 0 4px;letter-spacing:-.01em}
.sub{color:var(--mute);margin:0 0 14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:16px;margin:12px 0}
.verdict{display:flex;gap:14px;align-items:center}
.ring{--p:0;--c:var(--great);flex:none;width:68px;height:68px;border-radius:50%;display:grid;place-items:center;
background:conic-gradient(var(--c) calc(var(--p)*1%),var(--line) 0)}
.ring b{display:grid;place-items:center;width:54px;height:54px;border-radius:50%;background:var(--surface);font-size:1.3rem}
.great{--c:var(--great);color:var(--great)}.ok{--c:var(--ok);color:var(--ok)}.weak{--c:var(--weak);color:var(--weak)}
.vlabel{font-size:1.15rem;font-weight:700}.vsub{color:var(--mute);font-size:.92rem}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
.stat{background:var(--bg);border-radius:10px;padding:10px 8px;text-align:center}
.stat strong{display:block;font-size:1.1rem}.stat span{color:var(--mute);font-size:.78rem}
.actions{display:grid;grid-template-columns:2fr 1fr;gap:8px;margin-top:14px}
.btn{display:flex;align-items:center;justify-content:center;min-height:48px;border-radius:12px;font-weight:700;text-decoration:none;
padding:0 14px;text-align:center}
.btn.primary{background:var(--accent);color:var(--accent-ink)}.btn.secondary{border:1px solid var(--line);color:var(--ink);background:var(--surface)}
.tabs{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);display:flex;gap:4px;padding:8px 0;margin:8px 0 0;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabs button,.seg button{font:inherit;border:0;background:none;color:var(--mute);padding:9px 13px;border-radius:999px;white-space:nowrap;cursor:pointer;min-height:40px}
.tabs button[aria-selected=true]{background:var(--ink);color:var(--bg);font-weight:600}
.seg{display:flex;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:4px;gap:4px;margin:12px 0}
.seg button{flex:1;border-radius:9px;font-size:.92rem}.seg button[aria-selected=true]{background:var(--soft);color:var(--accent);font-weight:700}
h2{font-size:1.05rem;margin:22px 0 8px}
.list{list-style:none;padding:0;margin:0}.list li{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
.list li:last-child{border-bottom:0}
.dot{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:.75rem;font-weight:800;margin-top:1px}
.dot.good{background:var(--soft);color:var(--great)}.dot.ok{background:var(--warnbg);color:var(--ok)}
.dot.bad{background:var(--warnbg);color:var(--bad)}.dot.unknown{background:var(--bg);color:var(--mute)}
.note{background:var(--warnbg);color:var(--warn);border-radius:10px;padding:10px 12px;margin:10px 0;font-size:.93rem}
.summary{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.pill{display:inline-block;border-radius:999px;padding:2px 9px;font-size:.78rem;font-weight:600;background:var(--bg);color:var(--mute);margin:2px 4px 2px 0}
.pill.good{background:var(--soft);color:var(--great)}.pill.bad{background:var(--warnbg);color:var(--bad)}
.tl{list-style:none;padding:0;margin:8px 0 0;position:relative}
.tl>li{position:relative;padding:0 0 18px 28px}
.tl>li:before{content:"";position:absolute;left:8px;top:8px;bottom:-8px;width:2px;background:var(--line)}
.tl>li:last-child:before{display:none}
.tl>li:after{content:"";position:absolute;left:3px;top:5px;width:12px;height:12px;border-radius:50%;background:var(--accent);border:3px solid var(--bg)}
.day{font-size:.78rem;font-weight:700;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.leg{font-weight:700;margin:1px 0 4px}.stops{margin:6px 0;padding-left:18px}.stops li{margin:2px 0}
.camp{font-size:.9rem;color:var(--mute)}.small{font-size:.88rem;color:var(--mute)}
details{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:12px 0}
summary{cursor:pointer;font-weight:600}details ul{margin:8px 0 0;padding-left:18px}details li{margin:6px 0;font-size:.93rem}
table{width:100%;border-collapse:collapse}td{padding:9px 0;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}td:last-child{white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums;padding-left:10px}tr.total td{font-weight:800;border-bottom:0;font-size:1.05rem}
.minus{color:var(--great)}.na{color:var(--mute);font-style:italic}
dl{margin:0}dt{color:var(--mute);font-size:.82rem;margin-top:10px}dd{margin:2px 0 0}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.dealcard{display:block;color:inherit;text-decoration:none}.dealcard .row{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.score{flex:none;min-width:46px;text-align:center;border-radius:10px;padding:4px 6px;font-weight:800}
.score.great{background:var(--soft)}.score.ok{background:var(--warnbg)}.score.weak{background:var(--bg)}
.empty{text-align:center;color:var(--mute);padding:28px 10px}
footer{color:var(--mute);font-size:.82rem;margin-top:28px}
.js [role=tabpanel][hidden]{display:none}

body{font-size:17px}h1 .arrow{color:var(--mute);font-weight:500}
.answer{padding:18px}.trip{list-style:none;padding:0;margin:14px 0 0;border-top:1px solid var(--line)}
.trip li{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}.trip li:last-child{border-bottom:0;padding-bottom:0}
.trip .ic{flex:none;width:36px;height:36px;border-radius:10px;background:var(--soft);color:var(--accent);display:grid;place-items:center}.trip .k{font-size:.78rem;color:var(--mute);text-transform:uppercase;letter-spacing:.05em;font-weight:700}
.trip .v{font-weight:650;font-size:1.02rem}.trip .s,.steps .s{font-size:.85rem;color:var(--mute)}
h2.h{margin-top:22px}.steps{list-style:none;padding:0;margin:0}
.steps li{display:flex;gap:12px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:14px;margin:10px 0}
.steps .n{flex:none;width:30px;height:30px;border-radius:50%;background:var(--ink);color:var(--bg);display:grid;place-items:center;font-weight:800}
.steps .sb{flex:1;min-width:0}.steps .st{font-weight:700;margin-bottom:8px}.steps .btn{width:100%;min-height:52px;font-size:1rem}
.steps .s{margin-top:6px}.bring{margin:8px 0 0;padding-left:20px}.bring li{margin:6px 0}
tr.sub td{font-weight:700;border-bottom:0;color:var(--ink)}.cost{font-weight:650;margin:3px 0}
.best{border:2px solid var(--accent)}.eyebrow{font-size:.78rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
.sleep{margin:8px 0 4px;background:var(--bg);border-radius:10px;padding:8px 10px;display:grid;gap:5px}
.sleep .sl{font-size:.72rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--mute)}
.opt{display:flex;gap:8px;align-items:baseline;font-size:.9rem}
.tag{flex:none;font-size:.68rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;border-radius:6px;padding:1px 6px}
.tag.paid{background:var(--surface);color:var(--mute);border:1px solid var(--line)}.tag.free{background:var(--soft);color:var(--great)}
.topr{display:flex;align-items:center;gap:8px}.gear{display:grid;place-items:center;width:44px;height:44px;margin:-8px -10px -8px 0;border:0;border-radius:50%;background:transparent;color:var(--ink);cursor:pointer}
.gear:hover,.gear[aria-expanded=true]{background:var(--surface)}.gear:focus-visible,.close:focus-visible{outline:3px solid var(--accent)}
.settings h2{margin:0}.settings h3{font-size:.95rem;margin:16px 0 4px}.settings p{margin:0}.set-top{display:flex;justify-content:space-between;align-items:center}
.set-q{font-size:.85rem;color:var(--mute);margin-top:12px}.close{width:40px;height:40px;border:0;border-radius:50%;background:var(--bg);color:var(--ink);font-size:1.4rem;cursor:pointer}
.settings .seg{margin:6px 0 0}.settings .seg button[aria-pressed=true]{background:var(--soft);color:var(--accent);font-weight:700}
.why{font-size:.85rem;color:var(--bad);margin-top:2px}
.legc{display:block;font-size:.88rem;color:var(--mute);margin:2px 0}.bigcost{font-size:1.1rem;font-weight:700;margin:12px 0 4px}
"""

JS = """
document.documentElement.classList.add('js');
function pick(btn,push){var g=btn.closest('[role=tablist]');var tabs=g.querySelectorAll('[role=tab]');
tabs.forEach(function(t){var on=t===btn;t.setAttribute('aria-selected',on);t.tabIndex=on?0:-1;
document.getElementById(t.getAttribute('aria-controls')).hidden=!on;});
if(push&&g.dataset.hash){history.replaceState(null,'','#'+btn.dataset.key);}}
document.querySelectorAll('[role=tablist]').forEach(function(g){var tabs=[].slice.call(g.querySelectorAll('[role=tab]'));
tabs.forEach(function(t,i){t.addEventListener('click',function(){pick(t,true);});
t.addEventListener('keydown',function(e){var d=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;
if(d){var n=tabs[(i+d+tabs.length)%tabs.length];n.focus();pick(n,true);}});});
var want=(g.dataset.hash&&location.hash.slice(1))||g.dataset.default;var first=tabs.filter(function(t){return t.dataset.key===want;})[0]||tabs.filter(function(t){return t.dataset.key===g.dataset.default;})[0]||tabs[0];pick(first,false);});
window.addEventListener('hashchange',function(){var b=document.querySelector('[data-hash="1"] [role=tab][data-key="'+location.hash.slice(1)+'"]');if(b){pick(b,false);}});
document.querySelectorAll('[data-goto]').forEach(function(a){a.addEventListener('click',function(e){
var b=document.querySelector('[role=tab][data-key="'+a.dataset.goto+'"]');if(b){e.preventDefault();pick(b,true);
b.closest('.tabs').scrollIntoView({behavior:'smooth'});}});});
"""


def _head(title: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">'
            f'<title>{_e(title)}</title><style>{CSS}</style></head><body><main>')


def _tabs(group: str, items: list[tuple[str, str]], cls: str = "tabs", hash_: bool = True, default: str = "") -> str:
    btns = "".join(f'<button role="tab" id="b-{group}-{k}" data-key="{k}" aria-controls="p-{group}-{k}" '
                   f'aria-selected="{"true" if i == 0 else "false"}">{_e(label)}</button>'
                   for i, (k, label) in enumerate(items))
    return (f'<div class="{cls}" role="tablist" data-hash="{1 if hash_ else ""}" data-default="{_e(default)}" '
            f'aria-label="{_e(group)}">{btns}</div>')


def _panel(group: str, key: str, body: str) -> str:
    return f'<section role="tabpanel" id="p-{group}-{key}" aria-labelledby="b-{group}-{key}">{body}</section>'


def _overview(deal: Deal, sc: Score | None, opts, today: date) -> str:
    marks = {"good": "&#10003;", "ok": "!", "bad": "&#10005;", "unknown": "?"}
    why = "".join(f'<li><span class="dot {r}">{marks[r]}</span><span>{_e(t)}</span></li>'
                  for r, t in reasons(deal, sc, today))
    parts = [f'<h2>Why this score</h2><div class="card"><ul class="list">{why}</ul></div>']
    if opts:
        best = next((o for o in opts if o.fits_hours and o.fits_cap is not False), opts[0])
        fits = ("fits your nights with days under 5 hours" if best.fits_hours
                else "needs some long driving days")
        parts.append(
            f'<h2>Best route</h2><div class="card"><div class="summary"><div><strong>{_e(best.name)}</strong>'
            f'<div class="small">About {best.total_km:,.0f} km over {len(best.days)} days, {fits}.</div></div></div>'
            f'<p style="margin:10px 0 0"><a href="#itinerary" data-goto="itinerary">See the day-by-day plan</a>'
            + (f' &middot; {len(opts)} route options' if len(opts) > 1 else "") + "</p></div>")
    good_to_know = []
    o, d = split_places(deal.origin), split_places(deal.destination)
    if any(x in CANADA for x in o) != any(x in CANADA for x in d):
        good_to_know.append("Crosses the US / Canada border: passports (or NEXUS / enhanced licence) for everyone, "
                            f"and confirm the rental allows it ({CHECK}).")
    good_to_know += [n for n in deal.notes if not n.startswith(("seats:", "practice run", "site note"))]
    if deal.booking.startswith("phone"):
        good_to_know.append(f"Phone booking only: {deal.booking.split(': ', 1)[1]}.")
    if good_to_know:
        parts.append("<h2>Good to know</h2>" + "".join(f'<div class="note">{_e(g)}</div>' for g in good_to_know))
    return "".join(parts)


def _sleep(d) -> str:
    """Where to sleep that night: the paid campground and the free options near that town."""
    place = _place(d.end_key, d.end)
    free, note = free_options(d.end_key)
    rows = [f'<div class="opt"><span class="tag paid">Paid</span><a href="{_e(maps_search(d.camp + " " + place))}">{_e(d.camp)}</a></div>']
    for name, detail in free:
        rows.append(f'<div class="opt"><span class="tag free">Free</span><span><b>{_e(name)}</b>'
                    f'<span class="small"> &middot; {_e(detail)}</span></span></div>')
    if note:
        rows.append(f'<div class="small">{_e(note)}</div>')
    if free or (note and "outside town" in note):
        rows.append(f'<div class="small"><a href="{_e(maps_search("free camping near " + place))}">Find free spots near {_e(d.end.split(" (")[0])}</a></div>')
    return f'<div class="sleep"><div class="sl">Sleep options</div>{"".join(rows)}</div>'


def _itinerary(deal: Deal, opts, today: date, cfg: dict | None = None) -> str:
    if not opts:
        return ('<div class="card empty">No ready-made itinerary for this route yet.<br>'
                'The deal details are still accurate.</div>')
    out = []
    if len(opts) > 1:
        want = (cfg or {}).get("travel", {}).get("route_first", "scenic")
        first = next((f"r{i}" for i, o in enumerate(opts) if o.kind == want), "r0")
        tabs_html = _tabs("route", [(f"r{i}", o.name.split(" (")[0]) for i, o in enumerate(opts)], cls="seg",
                          hash_=False, default=first)
        for i, o in enumerate(opts):
            tabs_html = tabs_html.replace(f'data-key="r{i}"', f'data-key="r{i}" data-kind="{o.kind}"', 1)
        out.append(tabs_html)
    for i, op in enumerate(opts):
        pills = [f'<span class="pill">{op.total_km:,.0f} km</span>', f'<span class="pill">{len(op.days)} days</span>']
        pills.append('<span class="pill good">Days under 5 h</span>' if op.fits_hours
                     else '<span class="pill bad">Some long days</span>')
        if op.fits_cap is False:
            pills.append('<span class="pill bad">Over distance cap</span>')
        keys = [(op.days[0].start_key, op.days[0].start)] + [(d.end_key, d.end) for d in op.days if d.km > 0]
        body = [f'<div class="card"><div class="summary"><div><strong>{_e(op.name)}</strong>'
                f'<div class="chips">{"".join(pills)}</div></div></div>'
                + "".join(f'<div class="note">{_e(n)}</div>' for n in op.notes)
                + f'<p style="margin:10px 0 0"><a href="{_e(maps_route(keys))}">Open whole route in Google Maps</a></p></div>']
        alerts = list(dict.fromkeys(w for d in op.days for w in d.warnings))
        if alerts:
            body.append(f'<details><summary>Road and season alerts for your dates ({len(alerts)})</summary><ul>'
                        + "".join(f"<li>{_e(a)}</li>" for a in alerts)
                        + f'</ul><p class="small">Conditions change: {CHECK}.</p></details>')
        body.append(f'<div class="note">{_e(FREE_TIP)}</div>')
        days = []
        for d in op.days:
            if d.km == 0:
                days.append(f'<li><div class="day">Day {d.n}</div><div class="leg">Rest day in {_e(d.end)}</div>'
                            f'<ul class="stops">{"".join(f"<li>{_e(s)}</li>" for s in d.stops[1:] or d.stops)}</ul>'
                            + _sleep(d) + '</li>')
                continue
            long_ = d.hours > MAX_HOURS
            days.append(
                f'<li><div class="day">Day {d.n}</div><div class="leg">{_e(d.start)} &rarr; {_e(d.end)}</div>'
                f'<span class="pill">{d.km:,.0f} km</span><span class="pill {"bad" if long_ else ""}">{d.hours:g} h</span>'
                f'<ul class="stops">{"".join(f"<li>{_e(s)}</li>" for s in d.stops)}</ul>'
                + _sleep(d) +
                f'<div class="small"><a href="{_e(maps_route([(d.start_key, d.start), (d.end_key, d.end)]))}">Directions</a></div></li>')
        body.append(f'<h2>Day by day</h2><ol class="tl">{"".join(days)}</ol>'
                    f'<p class="small">Hours assume about {KMH} km/h with short breaks. Campground seasons, '
                    f'hours and reservations: {CHECK}.</p>')
        content = "".join(body)
        out.append(_panel("route", f"r{i}", content) if len(opts) > 1 else content)
    return "".join(out)


def _fine_print(deal: Deal, today: date) -> str:
    facts = [("Pick-up window, as listed", deal.pickup_text), ("Vehicle", deal.vehicle),
             ("Sleeps", deal.show("sleeps")), ("Penalty and cancellation terms", deal.penalty_terms),
             ("How to book", deal.booking), ("Deal ID", deal.deal_id)]
    shown = "".join(f"<dt>{_e(a)}</dt><dd>{_e(b)}</dd>" for a, b in facts if b and b != NOT_LISTED)
    missing_names = {"booking_fee": "booking fee", "bond": "bond", "included_distance_km": "distance allowance",
                     "fuel_allowance": "fuel allowance", "sleeps": "sleeping capacity", "penalty_terms": "penalty terms",
                     "extra_night_rate": "extra night rate", "excess_rate": "extra distance rate"}
    missing = [v for k, v in missing_names.items() if deal.show(k) == NOT_LISTED]
    miss = ""
    if missing:
        miss = (f'<h2>Not listed by {_e(deal.company)}</h2><div class="card"><div class="chips">'
                + "".join(f'<span class="pill">{_e(m)}</span>' for m in missing)
                + '</div><p class="small" style="margin:8px 0 0">Ask before you book. This tool never guesses these.</p></div>')
    return (f'<h2>Details</h2><div class="card"><dl>{shown}</dl>'
            f'<p style="margin:14px 0 0"><a href="{_e(deal.link)}">Original listing on {_e(deal.company)}</a></p></div>{miss}'
            f'<p class="small">Driving times, distances and campgrounds are approximate starting points. '
            f'Road closures, seasons, hours and reservations change: {CHECK}.</p>')


# ------------------------------------------------------------------ deal page

_SVG = {
    "when": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "fly": '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    "ground": '<rect x="4" y="3" width="16" height="15" rx="2"/><path d="M4 11h16M8 18v3M16 18v3"/>',
    "home": '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "rv": '<path d="M3 17V7a2 2 0 0 1 2-2h10l6 6v6h-2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6M15 5v6h6"/>',
    "money": '<circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.8 3 2 3 .9 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6v2M12 16v2"/>',
}


def _icon(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{_SVG[name]}</svg>')


def _book(deal: Deal, label_prefix: str = "") -> str:
    if deal.booking.startswith("phone"):
        num = deal.booking.split(": ", 1)[1]
        return f'<a class="btn primary" href="tel:{_e(num)}">{label_prefix}Call {_e(num)} to book</a>'
    return (f'<a class="btn primary" href="{_e(deal.link)}">{label_prefix}Book the RV on '
            f'{_e(deal.company.split(" + ")[0])}</a>')


def _ai(fmt: str, default: str) -> str:
    """A number Settings can recalculate (camping style, people). Shows the default until the script runs."""
    return f'<span class="ai" data-f="{fmt}">{_e(default)}</span>'


def _cost_attr(cost, deal: Deal) -> str:
    return f" data-cost='{_e(json.dumps(cost.model(deal.nights), separators=(',', ':')))}'" if cost else ""


def _trip_rows(deal: Deal, sc: Score | None, leg, cost, today: date) -> str:
    left = _days_left(deal, today)
    when_sub = ("Pick-up window has closed" if left is not None and left < 0
                else f"{left} days left to pick up" if left is not None else "")
    rows = [(_icon("when"), "When", _e(pickup_line(deal, today)), when_sub)]
    people = cost.people if cost else 1
    if leg:
        title = "Getting there" if leg.direction == "there" else "Getting home"
        if leg.low == 0 and leg.high == 0 and leg.mode == "ground":
            rows.append((_icon("home"), title, "You&#39;re already home", ""))
        elif not leg.high:
            rows.append((_icon("fly"), title, f"{_e(leg.summary)}, price not estimated", "real prices in step 2"))
        else:
            icon = _icon("fly") if leg.mode == "fly" else _icon("ground")
            each = range_text(leg.low, leg.high)
            hrs = f"about {leg.hours:g} h &middot; " if leg.hours else ""
            season = f"typical for {_e(leg.season)} &middot; " if leg.season else ""
            sub = (f"{hrs}around {_d(leg.when)} &middot; {season}"
                   + _ai("legline", f"{range_text(leg.low * people, leg.high * people)} for {people}")
                   + (" &middot; real prices in step 2" if leg.mode == "fly" else ""))
            rows.append((icon, title, f"{_e(leg.summary)}, {_e(each)} each", sub))
    pay, complete = estimate(deal)
    if pay is not None:
        rows.append((_icon("rv"), "The RV", _e(f"{_m(pay, deal.currency)} for {deal.nights} nights"),
                     "booking fee included" if complete else "booking fee not listed"))
    if cost:
        rows.append((_icon("money"), "All-in",
                     ("about " if cost.complete else "roughly ") + _ai("allin", range_text(cost.low, cost.high)),
                     _ai("pernight", range_text(cost.low / deal.nights, cost.high / deal.nights)) + " a night &middot; "
                     + _ai("style", CAMPING_STYLES[cost.style].split(",")[0].split(":")[0]) + " &middot; "
                     + _ai("people", f"{people} {'person' if people == 1 else 'people'}")))
    return f'<ul class="trip"{_cost_attr(cost, deal)}>' + "".join(
        f'<li><span class="ic" aria-hidden="true">{i}</span><div><div class="k">{k}</div>'
        f'<div class="v">{v}</div>'
        + (f'<div class="s">{s}</div>' if s else "") + "</div></li>" for i, k, v, s in rows) + "</ul>"


def _steps(deal: Deal, leg, opts) -> str:
    steps = [("Book the RV", _book(deal), "These go fast. The company confirms by email.")]
    if leg and leg.link:
        steps.append(("Book your flight", f'<a class="btn secondary" href="{_e(leg.link)}">See today\'s flight prices</a>',
                      "Wait for the RV confirmation before you buy."))
    elif leg and leg.mode == "ground" and leg.high:
        q = f"{leg.summary.split(',')[0]} {'from Vancouver to ' + leg.place if leg.direction == 'there' else 'from ' + leg.place + ' to Vancouver'}"
        steps.append(("Plan the trip " + ("there" if leg.direction == "there" else "home"),
                      f'<a class="btn secondary" href="{_e(maps_search(q))}">{_e(leg.summary.split(",")[0])}</a>',
                      "Book once the RV is confirmed."))
    best = next((o for o in opts if o.fits_hours), opts[0]) if opts else None
    if best:
        keys = [(best.days[0].start_key, best.days[0].start)] + [(d.end_key, d.end) for d in best.days if d.km > 0]
        steps.append(("Look at the route", f'<a class="btn secondary" href="{_e(maps_route(keys))}">Open the map</a>',
                      f"{best.name}, day by day plan below."))
    return '<ol class="steps">' + "".join(
        f'<li><div class="n">{i}</div><div class="sb"><div class="st">{_e(t)}</div>{b}<div class="s">{_e(s)}</div></div></li>'
        for i, (t, b, s) in enumerate(steps, 1)) + "</ol>"


def _bring(deal: Deal) -> str:
    items = ["Driver's licence (some companies want 2 years or more of driving)"]
    if deal.bond or deal.holding_deposit:
        amt = _m(deal.bond or deal.holding_deposit, deal.currency)
        items.append(f"A credit card with {amt} of room for the bond (held, then released)")
    else:
        items.append("A credit card for the bond (amount not listed: ask)")
    o, d = split_places(deal.origin), split_places(deal.destination)
    if any(x in CANADA for x in o) != any(x in CANADA for x in d):
        items.append("Passport (or NEXUS / enhanced licence) for everyone: this trip crosses the border")
    items.append("Bedding and towels unless the listing includes them")
    return '<ul class="bring">' + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _camp_how(paid: int, nights: int, per_night: float) -> str:
    free = nights - paid
    if not paid:
        return f"All {nights} nights free"
    return (f"{paid} paid night{'s' if paid != 1 else ''} at about CA${per_night:.0f}"
            + (f", {free} free" if free else ""))


def _money_tab(deal: Deal, leg, cost, cfg: dict) -> str:
    c = deal.currency
    rows = []
    pay, complete = estimate(deal)
    if deal.nightly_rate is not None and deal.nights:
        rows.append((f"RV: {deal.nights} nights &times; {_e(_m(deal.nightly_rate, c, cents=True))}",
                     _e(_m(deal.nightly_rate * deal.nights, c))))
    rows.append(("Booking fee", _e(_m(deal.booking_fee, c)) if deal.booking_fee is not None
                 else '<span class="na">not listed</span>'))
    trip = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows)
    trip += (f'<tr class="sub"><td>You pay {_e(deal.company.split(" + ")[0])}</td><td>{"~" if not complete else ""}'
             f'{_e(_m(pay, c)) if pay is not None else "?"}</td></tr>')

    allin = ""
    if cost:
        k = cfg.get("costs", {})
        lines = [("The RV", _e(money(cost.rv)))]
        if leg and (leg.high or leg.low):
            what = ("Flight " if leg.mode == "fly" else "Bus / ferry ") + ("there" if leg.direction == "there" else "home")
            sea = f", typical for {_e(leg.season)}" if leg.season else ""
            lines.append((f'{what}<div class="small">{_e(range_text(leg.low, leg.high))} each &times; '
                          f'{_ai("people", f"{cost.people} people" if cost.people != 1 else "1 person")}{sea}</div>',
                          _ai("leg", range_text(*cost.travel))))
        km = f"{cost.route_km:,.0f} km" if cost.route_km else "distance unknown"
        litre = cost.fuel_gross / max(1, (cost.route_km or 1) / 100 * k.get("rv_litres_per_100km", 28))
        fuel_note = (f"{km} at {k.get('rv_litres_per_100km', 28)} L/100 km, about CA${litre:.2f}/L"
                     + (f", minus {_m(deal.fuel_allowance, c)} refund" if deal.fuel_allowance else ""))
        lines.append((f'Fuel<div class="small">{_e(fuel_note)}</div>', _e(money(cost.fuel))))
        st = cost.by_style[cost.style]
        lines.append((f'Sleeping<div class="small">{_ai("camphow", _camp_how(st["paid_nights"], deal.nights, cost.camp_per_night))}</div>',
                      _ai("camp", money(st["camping"]))))
        body = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in lines)
        allin = (f'<h2>All-in estimate</h2><div class="card"{_cost_attr(cost, deal)}><table>{body}'
                 f'<tr class="total"><td>Total</td><td>{_ai("allin", range_text(cost.low, cost.high))}</td></tr></table>'
                 f'<p class="small" style="margin:6px 0 0">Canadian dollars. How you sleep and how many people are '
                 f'travelling are in Settings (the gear on the deals list). Fares, fuel and campground prices are '
                 f'estimates for the season. Food and insurance extras not included.</p></div>')

    held = [("Bond (held, released after return)", deal.bond), ("Holding deposit", deal.holding_deposit)]
    held_rows = "".join(f'<tr><td>{a}</td><td>{_e(_m(v, c)) if v is not None else "<span class=na>not listed</span>"}</td></tr>'
                        for a, v in held)
    more = [("Extra nights", f"{_m(deal.extra_night_rate, c)}/night" + (f", up to {deal.extra_nights}" if deal.extra_nights else "")
             if deal.extra_night_rate is not None else None),
            ("Extra distance", deal.excess_rate if deal.excess_rate != NOT_LISTED else None)]
    more_rows = "".join(f'<tr><td>{a}</td><td>{_e(v) if v else "<span class=na>not listed</span>"}</td></tr>' for a, v in more)
    cur = {"USD": "US dollars", "CAD": "Canadian dollars"}.get(c, c if c != NOT_LISTED else "a currency the site doesn't state")
    return (allin + f'<h2>Paid to the company</h2><div class="card"><table>{trip}</table>'
            f'<p class="small" style="margin:6px 0 0">In {_e(cur)}.</p></div>'
            f'<h2>Held on your card</h2><div class="card"><table>{held_rows}</table></div>'
            f'<h2>If you want more</h2><div class="card"><table>{more_rows}</table></div>')


def render_plan(deal: Deal, sc: Score | None, today: date, cfg: dict | None = None) -> str:
    cfg = cfg or DEFAULT_CFG
    opts = options_for(deal, today)
    leg = leg_for(deal, cfg, today)
    best = next((o for o in opts if o.fits_hours), opts[0]) if opts else None
    # same distance as the text message and the score (direct route), so the numbers always match
    cost = all_in(deal, cfg, leg, (sc.route_km if sc and sc.route_km else (best.total_km if best else None)))
    total = sc.total if sc else 0
    label, cls = verdict(total)
    nights = f"{deal.nights} nights" if deal.nights else "Nights not listed"
    line = (f"{_e(nights)}, about {_ai('allin', range_text(cost.low, cost.high))} all-in" if cost else _e(nights))
    sleeps = f" &middot; sleeps {deal.sleeps}" if deal.sleeps else ""
    head = (f'<div class="top"><a href="../">&larr; All deals</a><span>{_e(deal.company)}</span></div>'
            f'<h1>{_e(deal.origin)} <span class="arrow">&rarr;</span> {_e(deal.destination)}</h1>'
            f'<p class="sub">{_e(deal.vehicle if deal.vehicle != NOT_LISTED else "Vehicle not listed")}{sleeps}</p>'
            f'<div class="card answer"><div class="verdict"><div class="ring {cls}" style="--p:{total}"><b>{total}</b></div>'
            f'<div><div class="vlabel {cls}">{label}</div><div class="vsub"{_cost_attr(cost, deal)}>{line}</div></div></div>'
            f'{_trip_rows(deal, sc, leg, cost, today)}</div>'
            f'<h2 class="h">Grab it in {3 if (leg and (leg.link or leg.high)) and best else 2} steps</h2>{_steps(deal, leg, opts)}'
            f'<details class="bringbox"><summary>What to bring</summary>{_bring(deal)}</details>')
    tabs = _tabs("deal", [("overview", "Why this score"), ("itinerary", "Day by day"), ("costs", "Money"),
                          ("details", "Fine print")])
    panels = (_panel("deal", "overview", _overview(deal, sc, opts, today))
              + _panel("deal", "itinerary", _itinerary(deal, opts, today, cfg))
              + _panel("deal", "costs", _money_tab(deal, leg, cost, cfg))
              + _panel("deal", "details", _fine_print(deal, today)))
    return (_head(f"{deal.origin} to {deal.destination}") + head + '<div id="more"></div>' + tabs + panels
            + f'<footer>RV Deal Hunter &middot; updated {today:%b %d, %Y} &middot; estimates, {CHECK}</footer>'
            f'</main><script>{JS}{PREFS_JS}</script></body></html>')


# ------------------------------------------------------------------ deals list

def _deal_card(e: dict, today: date, big: bool = False) -> str:
    score = int(e.get("score", 0))
    label, cls = verdict(score)
    last = date.fromisoformat(e["last_day"]) if e.get("last_day") else None
    left = (last - today).days if last else None
    when = e.get("when") or e.get("pickup", "")
    bits = [when] + ([f'{e["nights"]} nights'] if e.get("nights") else [])
    m = e.get("cost")
    cost_attr = f" data-cost='{_e(json.dumps(m, separators=(',', ':')))}'" if m else ""
    cost = []
    if e.get("allin_low") is not None:
        cost.append("~" + _ai("allin", range_text(e["allin_low"], e.get("allin_high") or e["allin_low"])) + " all-in")
    if e.get("leg_cost"):
        what = "Flight" if "Flight" in (e.get("leg") or "") else "Bus/ferry"
        cost.append(f'<span class="legc">{what} {_e(e["leg_cost"])} each</span>')
    chip = ""
    if left is not None and 0 <= left <= 14:
        chip = f'<span class="pill {"bad" if left <= 7 else ""}">closes in {left} day{"s" if left != 1 else ""}</span>'
    why = f'<div class="why">{_e(e["why"])}</div>' if e.get("why") and score < 40 else ""
    twins = f'<span class="pill">{e["twins"]} RVs</span>' if e.get("twins", 1) > 1 else ""
    route = f'{_e(e.get("origin") or e.get("route", ""))}' + (f' &rarr; {_e(e["destination"])}' if e.get("destination") else "")
    if big:
        return (f'<a class="card dealcard best" href="p/{_e(e["id"])}.html"{cost_attr}><div class="eyebrow">Best right now</div>'
                f'<div class="verdict"><div class="ring {cls}" style="--p:{score}"><b>{score}</b></div>'
                f'<div><div class="leg" style="font-size:1.2rem">{route}</div>'
                f'<div class="small">{_e(" · ".join(bits))}</div></div></div>'
                f'<div class="bigcost">{cost[0] if cost else ""}</div>{cost[1] if len(cost) > 1 else ""}{chip}'
                f'<div class="btn primary" style="margin-top:12px">See this deal</div></a>')
    return (f'<a class="card dealcard" href="p/{_e(e["id"])}.html"{cost_attr}><div class="row"><div>'
            f'<strong>{route}</strong>'
            f'<div class="small">{_e(" · ".join(bits))}</div>'
            + (f'<div class="cost">{cost[0]}</div>' if cost else "") + (cost[1] if len(cost) > 1 else "")
            + f'<div class="small">{_e(e.get("company", ""))}</div>{why}{twins}{chip}</div>'
            f'<div class="score {cls}">{score}</div></div></a>')


PREFS_JS = r"""
var RV_LABELS={campgrounds:'Campgrounds every night',mix:'Mix',free:'Mostly free'};
function rvGet(k,d){try{return localStorage.getItem('rvdh-'+k)||d;}catch(e){return d;}}
function rvSet(k,v){try{localStorage.setItem('rvdh-'+k,v);}catch(e){}}
function rvMoney(v){v=Math.max(0,v);return v>=100?'$'+(Math.round(v/10)*10).toLocaleString('en-US'):'$'+Math.round(v);}
function rvRange(a,b){return Math.round(a/10)===Math.round(b/10)?rvMoney(a):rvMoney(a)+'-'+rvMoney(b).slice(1);}
function rvApply(root){root=root||document;
root.querySelectorAll('[data-cost]').forEach(function(box){var m;try{m=JSON.parse(box.getAttribute('data-cost'));}catch(e){return;}
var c=rvGet('camp',m.dc);if(!(c in m.paid))c=m.dc;var p=parseInt(rvGet('people',m.dp),10)||m.dp;
var paid=m.paid[c],cs=paid*m.cpn,lo=m.rv+m.tl*p+m.fuel+cs,hi=m.rv+m.th*p+m.fuel+cs,fr=m.n-paid;
var out={allin:rvRange(lo,hi),pernight:rvRange(lo/m.n,hi/m.n),leg:rvRange(m.tl*p,m.th*p),legline:rvRange(m.tl*p,m.th*p)+' for '+p,
people:p+(p===1?' person':' people'),style:RV_LABELS[c],camp:rvMoney(cs),
camphow:paid?paid+' paid night'+(paid===1?'':'s')+' at about CA$'+Math.round(m.cpn)+(fr?', '+fr+' free':''):'All '+m.n+' nights free'};
box.querySelectorAll('.ai').forEach(function(s){if(s.closest('[data-cost]')===box&&out[s.dataset.f]!==undefined)s.textContent=out[s.dataset.f];});});
var rf=rvGet('route','');if(rf&&typeof pick==='function')root.querySelectorAll('[data-kind="'+rf+'"]').forEach(function(b){pick(b);});}
(function(){var g=document.getElementById('gear'),pn=document.getElementById('settings');if(!g||!pn)return;
function open(o){pn.hidden=!o;g.setAttribute('aria-expanded',o);}
g.addEventListener('click',function(){open(pn.hidden);});
document.getElementById('set-close').addEventListener('click',function(){open(false);g.focus();});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!pn.hidden){open(false);g.focus();}});
function sync(){pn.querySelectorAll('[data-pref]').forEach(function(b){b.setAttribute('aria-pressed',rvGet(b.dataset.pref,b.dataset.def)===b.dataset.val);});}
pn.querySelectorAll('[data-pref]').forEach(function(b){b.addEventListener('click',function(){rvSet(b.dataset.pref,b.dataset.val);sync();rvApply(document);});});
sync();})();
rvApply(document);
"""

GEAR = ('<button class="gear" id="gear" aria-label="Settings" aria-expanded="false" aria-controls="settings">'
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>')


def _settings(cfg: dict | None) -> str:
    cfg = cfg or {}
    camp = (cfg.get("costs") or {}).get("camping_style", "free")
    people = str((cfg.get("travel") or {}).get("travellers", 2))
    route = (cfg.get("travel") or {}).get("route_first", "scenic")

    def group(pref, default, opts, label):
        btns = "".join(f'<button type="button" data-pref="{pref}" data-val="{v}" data-def="{default}">{_e(t_)}</button>'
                       for v, t_ in opts)
        return f'<div class="set-q">{_e(label)}</div><div class="seg" role="group" aria-label="{_e(label)}">{btns}</div>'
    return ('<section class="card settings" id="settings" hidden aria-labelledby="set-h">'
            '<div class="set-top"><h2 id="set-h">Settings</h2><button class="close" id="set-close" aria-label="Close settings">&times;</button></div>'
            + group("camp", camp, [("free", "Mostly free"), ("mix", "Mix"), ("campgrounds", "Campgrounds")], "How will you sleep?")
            + group("people", people, [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")], "People travelling (flights are per person)")
            + group("route", route, [("scenic", "Scenic"), ("fast", "Fast")], "Which route to show first")
            + '<p class="small" style="margin-top:10px">Changes every price on every deal right away. Scores and texts '
              'use the same settings in config.yaml.</p>'
            + '<h3>About this page</h3><p class="small" id="about"><!--about-->Checks Imoova, CanaDream, CanaDream + El Monte RV '
              'and Fraserway at 7am and 1pm Pacific. Flight, fuel and campground costs are estimates for the time of '
              'year.<!--/about--></p></section>')


def _group_twins(entries: list[dict]) -> list[dict]:
    """Same route, dates, nights and score (a company listing several identical RVs): one card, with a count."""
    out, seen = [], {}
    for e in entries:
        key = (e.get("company"), e.get("origin"), e.get("destination"), e.get("when"), e.get("nights"), e.get("score"))
        if key in seen:
            seen[key]["twins"] = seen[key].get("twins", 1) + 1
            continue
        seen[key] = e = dict(e)
        out.append(e)
    return out


def render_index(entries: list[dict], today: date, text_now: int = 70, min_score: int = 40, cfg: dict | None = None) -> str:
    entries = _group_twins(sorted(entries, key=lambda e: (-int(e.get("score", 0)), e.get("id", ""))))
    shown = [e for e in entries if int(e.get("score", 0)) >= min_score]
    skipped = [e for e in entries if int(e.get("score", 0)) < min_score]

    def left(e):
        return (date.fromisoformat(e["last_day"]) - today).days if e.get("last_day") else 999
    groups = [
        ("top", "Great", [e for e in shown if int(e.get("score", 0)) >= text_now],
         "No great deals right now. You'll get a text the moment one appears."),
        ("digest", "Good", [e for e in shown if int(e.get("score", 0)) < text_now],
         f"Nothing in the {min_score} to {text_now - 1} range right now."),
        ("soon", "Closing", sorted([e for e in shown if 0 <= left(e) <= 14], key=left),
         "No deals closing in the next two weeks."),
        ("all", "All", shown, "No matching deals right now."),
        ("skipped", "Skipped", skipped, "Nothing skipped: every deal on your routes is worth a look."),
    ]
    hero = _deal_card(shown[0], today, big=True) if shown else ""
    tabs = _tabs("list", [(k, f"{label} {len(items)}") for k, label, items, _ in groups])
    panels = "".join(_panel("list", k, ("" if k != "skipped" or not items else
                                        f'<p class="small">On your routes but scored under {min_score}: no text, '
                                        f'shown here so you can see why.</p>')
                            + ("".join(_deal_card(e, today) for e in items) or f'<div class="card empty">{_e(empty)}</div>'))
                     for k, _, items, empty in groups)
    how = ('<details><summary>How this works</summary><ul>'
           '<li>Checks Imoova, CanaDream, CanaDream + El Monte RV and Fraserway at 7am and 1pm.</li>'
           f'<li>Scores {text_now} or more are texted right away. {min_score} to {text_now - 1} come in one text at 6pm. '
           'Lower ones are listed under Skipped.</li>'
           '<li>"All-in" adds the RV, flights or bus for everyone travelling, fuel and camping. It\'s an estimate.</li>'
           f'<li>Road conditions, campgrounds and prices change: {CHECK}.</li></ul></details>')
    return (_head("RV Deal Hunter")
            + f'<div class="top"><span>RV Deal Hunter</span><span class="topr">Updated {today:%b %d}{GEAR}</span></div>'
            + _settings(cfg)
            + f'<h1>RV deals for you</h1><p class="sub">One-way RV relocations on your routes, '
              f'best first. Tap one to see the plan.</p>'
            + hero + tabs + panels + how
            + f'<footer>Scores and costs are estimates: {CHECK}.</footer></main><script>{JS}{PREFS_JS}</script></body></html>')


# ------------------------------------------------------------------ files

def _new_tab(html_: str) -> str:
    """Outside links open in a new tab, so the deal page stays open behind them."""
    return re.sub(r'<a ((?:(?!href=)[^>])*)href="https://', r'<a \1target="_blank" rel="noopener" href="https://', html_)


def write_plan(docs: Path, deal: Deal, sc: Score | None, today: date, cfg: dict | None = None) -> Path:
    p = Path(docs) / "p" / f"{deal.deal_id}.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_new_tab(render_plan(deal, sc, today, cfg)))
    return p


def prune_pages(docs: Path, seen: dict, today: date, keep_days: int = 14) -> int:
    """Delete plan pages for deals that closed more than keep_days ago (or were forgotten)."""
    removed = 0
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    for f in (Path(docs) / "p").glob("*.html"):
        info = seen.get(f.stem)
        if info is None or info.get("last_day", "9999") < cutoff:
            f.unlink()
            removed += 1
    return removed


def write_index(docs: Path, seen: dict, today: date, min_score: int, text_now: int = 70,
                cfg: dict | None = None) -> None:
    entries = [dict(id=k, **v) for k, v in seen.items()
               if v.get("last_day", "0") >= today.isoformat() and (Path(docs) / "p" / f"{k}.html").exists()]
    Path(docs).mkdir(parents=True, exist_ok=True)
    (Path(docs) / "index.html").write_text(_new_tab(render_index(entries, today, text_now, min_score, cfg)))
