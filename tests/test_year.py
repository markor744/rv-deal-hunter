"""The year simulator as a test: two full simulated years (different seasons, seeds and
start dates) must pass every check. See rvdeals/simulate.py for what each run throws at the tool."""
from datetime import date
from pathlib import Path

import pytest
import yaml

from rvdeals import simulate
from rvdeals.textutil import parse_day_month

CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())


@pytest.mark.parametrize("start,seed", [(date(2026, 11, 22), 7), (date(2027, 6, 15), 2)])
def test_a_whole_year(start, seed):
    full = simulate.all_texts_on(CFG)
    sim = simulate.run(start, 365, full, seed)
    failed = [(name, detail) for name, ok, detail in simulate.check(sim, full) if not ok]
    assert not failed


@pytest.mark.parametrize("start,seed", [(date(2026, 11, 22), 7), (date(2027, 6, 15), 2)])
def test_a_whole_year_with_your_settings(start, seed):
    sim = simulate.run(start, 365, CFG, seed)
    failed = [(name, detail) for name, ok, detail in simulate.check_your_settings(sim, CFG) if not ok]
    assert not failed


def test_leap_day_without_a_year():
    assert parse_day_month("29 Feb", date(2027, 7, 19)) == date(2028, 2, 29)
