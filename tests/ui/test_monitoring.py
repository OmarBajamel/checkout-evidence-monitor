"""Future loopback-only UI verification. No merchant request is permitted by the fixture."""

import json
import pytest
from playwright.sync_api import expect
from tests.ui.test_workbench import workbench as original_workbench


@pytest.fixture
def workbench(tmp_path, root):
    yield from original_workbench.__wrapped__(tmp_path, root)


def test_guided_setup_saves_paused_without_network_collection(workbench):
    page, *_ = workbench
    external = []
    page.on(
        "request",
        lambda r: external.append(r.url) if not r.url.startswith("http://127.0.0.1:8760/") else None,
    )
    page.get_by_role("button", name="Monitoring", exact=True).click()
    page.get_by_role("button", name="Set up store", exact=True).click()
    dialog = page.get_by_role("dialog", name="Set up an authorized store")
    dialog.get_by_label("Store name", exact=True).fill("Synthetic pilot setup")
    dialog.get_by_label("Store origin", exact=True).fill("https://store.example.com")
    dialog.get_by_label("Authorizing operator", exact=True).fill("Synthetic test operator")
    dialog.get_by_role("button", name="Continue", exact=True).click()
    dialog.get_by_label("Visible CSS selector", exact=False).fill("main")
    dialog.get_by_role("button", name="Continue", exact=True).click()
    dialog.get_by_role("button", name="Continue", exact=True).click()
    dialog.get_by_role("checkbox").check()
    dialog.get_by_role("button", name="Save paused target", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.locator(".target-card")).to_contain_text("PAUSED")
    expect(page.get_by_role("button", name="Run once", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Start cadence", exact=True)).to_be_disabled()
    assert external == []


def test_review_decision_and_export_keep_pair_context(workbench, tmp_path):
    page, a, b, *_ = workbench
    page.evaluate(
        '(path)=>{history.pushState(null,"",path);dispatchEvent(new PopStateEvent("popstate"))}',
        "/changes?baseline=" + a.id + "&candidate=" + b.id,
    )
    page.get_by_label("Reason · 3–500 characters", exact=True).fill("Synthetic release-owner review")
    page.get_by_role("button", name="Record decision", exact=True).click()
    expect(page.locator(".review-history")).to_contain_text("Synthetic release-owner review")
    with page.expect_download() as saved:
        page.get_by_role("button", name="Export review", exact=True).click()
    path = tmp_path / "review.json"
    saved.value.save_as(path)
    result = json.loads(path.read_text())
    assert result["baseline"]["id"] == a.id and result["candidate"]["id"] == b.id
    assert result["reviews"][0]["reason"] == "Synthetic release-owner review"


def test_operational_views_reflow_and_keep_four_primary_destinations(workbench):
    page, *_ = workbench
    expect(page.get_by_role("navigation", name="Primary").get_by_role("link")).to_have_count(4)
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        for name in ("Monitoring", "Inbox", "Recorded visits"):
            page.get_by_role("button", name=name, exact=True).click()
            expect(page.get_by_role("button", name=name, exact=True)).to_have_attribute(
                "aria-pressed", "true"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
