"""Site readers. Each has collect(fetcher, today, wanted, seen_ids, max_details) -> list[Deal].

Cruise America / Cruise Canada is deliberately absent: its terms of use forbid robots and
data gathering (checked 2026-11-22)."""
from . import canadream, canadream_elmonte, fraserway, imoova

SOURCES = {
    "imoova": imoova,
    "canadream": canadream,
    "canadream_elmonte": canadream_elmonte,
    "fraserway": fraserway,
}
