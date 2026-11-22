"""The Deal record every source produces. Missing values are NOT_LISTED, never guessed."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional

NOT_LISTED = "not listed"


@dataclass
class Deal:
    company: str
    deal_id: str
    origin: str                      # as the site shows it, e.g. "Toronto / Montreal"
    destination: str
    link: str
    pickup_from: Optional[date] = None   # earliest pick-up
    pickup_to: Optional[date] = None     # latest pick-up (or the drop-off deadline when that is all the site gives)
    pickup_text: str = NOT_LISTED        # the window as the site words it
    nights: Optional[int] = None         # nights at the relocation rate
    extra_nights: Optional[int] = None   # further nights you may add (usually at a higher rate)
    currency: str = NOT_LISTED           # "CAD" / "USD"
    nightly_rate: Optional[float] = None
    extra_night_rate: Optional[float] = None
    booking_fee: Optional[float] = None
    bond: Optional[float] = None
    holding_deposit: Optional[float] = None
    included_distance_km: Optional[float] = None   # None = not listed; float("inf") = unlimited
    excess_rate: str = NOT_LISTED                 # e.g. "CA$0.47 / km"
    fuel_allowance: Optional[float] = None
    fuel_text: str = NOT_LISTED
    ferry_allowance: Optional[float] = None
    vehicle: str = NOT_LISTED
    sleeps: Optional[int] = None
    penalty_terms: str = NOT_LISTED
    booking: str = "online"            # "online" or "phone: 1-800-..."
    notes: list[str] = field(default_factory=list)

    def show(self, name: str) -> str:
        """Human text for a field, 'not listed' when missing."""
        v = getattr(self, name)
        if v is None or v == "":
            return NOT_LISTED
        if isinstance(v, float) and v == float("inf"):
            return "unlimited"
        if isinstance(v, date):
            return v.isoformat()
        return str(v)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, date):
                d[k] = v.isoformat()
            if isinstance(v, float) and v == float("inf"):
                d[k] = "unlimited"
        return d

    def __post_init__(self):
        # deal_id and link come from scraped pages. deal_id becomes a file name and part of a URL,
        # so keep only safe characters; link goes into href=, so allow only web addresses.
        self.deal_id = re.sub(r"[^A-Za-z0-9._-]", "-", str(self.deal_id)).lstrip(".-") or "deal"
        if not re.match(r"^https?://", str(self.link or ""), re.I):
            self.link = ""
