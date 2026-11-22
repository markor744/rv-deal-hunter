"""Small parsing helpers shared by the site readers."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def page_text(html: str) -> str:
    s = soup(html)
    for t in s(["script", "style", "noscript", "svg"]):
        t.decompose()
    return clean(s.get_text(" "))


def money(s: str | None) -> tuple[float | None, str]:
    """'CA$1,234.50' -> (1234.5, 'CAD'); '$19.00' -> (19.0, '') ; nothing -> (None, '')."""
    if not s:
        return None, ""
    m = re.search(r"(CA\$|C\$|CAD\s*\$?|US\$|USD\s*\$?|\$)\s*([\d,]+(?:\.\d+)?)", s)
    if not m:
        return None, ""
    sym = m.group(1).upper()
    cur = "CAD" if sym.startswith("C") else "USD" if sym.startswith("U") else ""
    return float(m.group(2).replace(",", "")), cur


def _year_for(month: int, day: int, today: date) -> int:
    """Sites often omit the year: pick the next occurrence (allowing ~2 months in the past)."""
    for y in range(today.year, today.year + 5):   # 29 Feb only exists in leap years
        try:
            if (date(y, month, day) - today).days >= -60:
                return y
        except ValueError:
            continue
    return today.year


def parse_day_month(text: str, today: date, year: int | None = None) -> date | None:
    """'23rd Nov 2026', '23 Nov', '1 Apr 27', '19 November 2026' -> date."""
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?(?:\s+(\d{2,4}))?", text or "")
    if not m:
        return None
    mon = MONTHS.get(m.group(2)[:3].lower())
    if not mon:
        return None
    day = int(m.group(1))
    y = m.group(3)
    if y:
        year = int(y) + (2000 if len(y) == 2 else 0)
    if year is None:
        year = _year_for(mon, day, today)
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def parse_range(text: str, today: date) -> tuple[date | None, date | None]:
    """'23 Nov - 2 Dec', '1 - 24 Apr 27', '21 Nov - 30 Nov' -> (start, end)."""
    text = clean(text)
    parts = re.split(r"\s+[-–]\s+|\s+to\s+", text, maxsplit=1)
    if len(parts) != 2:
        d = parse_day_month(text, today)
        return d, None
    a, b = parts
    end = parse_day_month(b, today)
    if end is None:
        return parse_day_month(a, today), None
    if re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", a.strip()):        # '1 - 24 Apr 27'
        a = f"{a.strip()} {end.strftime('%b')} {end.year}"
    start = parse_day_month(a, today, year=None)
    if start and not re.search(r"\d{4}|\s\d{2}$", a.strip()):
        # start had no year: it is the same year as end, or the year before
        start = start.replace(year=end.year)
        if start > end:
            start = start.replace(year=end.year - 1)
    return start, end
