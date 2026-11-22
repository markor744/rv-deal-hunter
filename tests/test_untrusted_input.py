"""Scraped values must not break out of the plan folder or inject script links."""
from datetime import date

from rvdeals import pages
from rvdeals.models import Deal


def _deal(**kw):
    base = dict(company="Imoova", deal_id="RLC1", origin="Seattle", destination="Vancouver",
                link="https://www.imoova.com/relocations/RLC1")
    base.update(kw)
    return Deal(**base)


def test_deal_id_cannot_escape_the_plans_folder(tmp_path):
    d = _deal(deal_id="../../evil")
    assert "/" not in d.deal_id and not d.deal_id.startswith(".")
    p = pages.write_plan(tmp_path, d, None, date(2026, 11, 22))
    assert p.resolve().parent == (tmp_path / "p").resolve()


def test_normal_deal_ids_are_unchanged():
    for i in ("RLC126667", "CDEM-vancouver-seattle-2026-11-30", "FW-page-3", "CD-calgary-vancouver"):
        assert _deal(deal_id=i).deal_id == i


def test_script_links_are_dropped():
    d = _deal(link="javascript:alert(1)")
    assert d.link == ""
    html = pages.render_plan(d, None, date(2026, 11, 22))
    assert "javascript:" not in html
