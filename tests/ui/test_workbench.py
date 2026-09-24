import json
import threading
import time
import pytest
import uvicorn
from playwright.sync_api import sync_playwright, expect
from cem.api import Session, create_app
from cem.storage import Store
from cem.phase import source_snapshot
from tests.helpers import run, script


@pytest.fixture
def workbench(tmp_path, root):
    store = Store(tmp_path / "ui-records")
    first = run(script())
    first.label = "Synthetic baseline"
    a = store.save(first)
    record = run(script(body=b"updated"), script("extra"))
    record.label = "Synthetic candidate"
    record.evidence[0].integrity_metadata = "<img src=x onerror=alert(1)>"
    b = store.save(record)
    b2 = run(script())
    b2.label = "Synthetic consent variant"
    b2.profile.consent = "ACCEPTED"
    mismatch = store.save(b2)
    limited = run(script("missing-body"))
    limited.label = "Synthetic partial record"
    limited.status = "PARTIAL"
    limited.limitation_codes = ["BODY_UNAVAILABLE"]
    limited.evidence[0].body_sha256 = None
    limited.evidence[0].body_size = None
    limited.evidence[0].body_representation = None
    limited.evidence[0].body_reason = "BODY_UNAVAILABLE"
    partial = store.save(limited)
    session = Session()
    bootstrap = session.bootstrap
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(store, session, 8760),
            host="127.0.0.1",
            port=8760,
            access_log=False,
            log_config=None,
            log_level="critical",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started, "Local test server did not start; no fallback port or external server used"
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--disable-background-networking", "--disable-sync"]
            )
            environment = root / "reports/testing/browser_environment.json"
            environment.parent.mkdir(parents=True, exist_ok=True)
            environment.write_text(
                json.dumps(
                    {
                        "actual_browser_version": browser.version,
                        "channel": "task-local Chromium headless shell",
                        "playwright": "1.63.0",
                        "scope": "loopback UI only",
                        "source_snapshot": source_snapshot(root),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            try:
                context = browser.new_context(reduced_motion="reduce", accept_downloads=True)
                context.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.url.startswith("http://127.0.0.1:8760/")
                    else route.abort(),
                )
                page = context.new_page()
                page.goto("http://127.0.0.1:8760/#bootstrap=" + bootstrap)
                expect(page.get_by_role("heading", name="Assessments", exact=True)).to_be_visible()
                yield page, a, b, mismatch, partial
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive(), "Owned UI server did not shut down"


def test_T28_actual_baseline_comparison_filter_and_export(workbench, tmp_path):
    page, a, b, _, _ = workbench
    row = page.locator("tr").filter(has=page.get_by_role("button", name=a.label, exact=True))
    row.get_by_role("button", name="Select baseline", exact=True).click()
    page.get_by_label("Selection reason").fill("Synthetic UI verification baseline")
    page.get_by_role("button", name="Confirm baseline", exact=True).click()
    expect(row.get_by_text("Selected baseline", exact=True)).to_be_visible()
    page.get_by_label("Select " + a.label, exact=True).check()
    page.get_by_label("Select " + b.label, exact=True).check()
    page.get_by_role("button", name="Compare selected", exact=False).click()
    page.get_by_role("button", name="ADDED", exact=True).click()
    expect(page.locator(".change-row")).to_have_count(1)
    page.locator(".change-row").first.click()
    expect(page.locator(".evidence-panel")).to_contain_text("extra.js")
    page.get_by_role("button", name="Open evidence record", exact=False).click()
    with page.expect_download() as saved:
        page.get_by_role("button", name="Export report", exact=False).click()
    target = tmp_path / "ui-export.html"
    saved.value.save_as(target)
    html = target.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html and "<script" not in html
    assert "synthetic-secret" not in html


def test_T29_keyboard_navigation_dialog_and_widths(workbench, root):
    page, a, b, _, _ = workbench
    page.keyboard.press("Tab")
    expect(page.get_by_text("Skip to evidence workspace")).to_be_focused()
    trigger = page.get_by_role("button", name="Select baseline", exact=True).first
    trigger.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("dialog", name="Select a baseline")).to_be_visible()
    expect(page.get_by_label("Selection reason")).to_be_focused()
    modal_records = []
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        bounds = page.get_by_role("dialog").bounding_box()
        assert bounds is not None
        assert abs(bounds["x"] + bounds["width"] / 2 - width / 2) <= 2
        assert abs(bounds["y"] + bounds["height"] / 2 - height / 2) <= 2
        assert bounds["x"] >= 15 and bounds["y"] >= 15
        path = root / "reports/screenshots" / f"baseline-dialog-{width}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        modal_records.append(
            {
                "file": path.relative_to(root).as_posix(),
                "viewport": [width, height],
                "bounds": bounds,
                "fixture": "Synthetic baseline selection; DECLARED_IMPORT",
                "caption": "SYNTHETIC FIXTURE SCREENSHOT",
                "source_snapshot": source_snapshot(root),
                "visual_review": "PENDING_IMAGE_INSPECTION",
            }
        )
    (root / "reports/screenshots/dialog-manifest.json").write_text(
        json.dumps(modal_records, indent=2), encoding="utf-8"
    )
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Select a baseline")).not_to_be_visible()
    expect(trigger).to_be_focused()
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("link", name="Changes").click()
    expect(page.get_by_label("Baseline", exact=True)).to_be_visible()
    page.get_by_label("Baseline", exact=True).select_option(a.id)
    page.get_by_label("Candidate", exact=True).select_option(b.id)
    expect(page.get_by_role("button", name="ALL", exact=True)).to_be_visible()


def test_T30_empty_error_partial_long_text(workbench):
    page, _, _, _, partial = workbench
    page.evaluate(
        '(path)=>{history.pushState(null,"",path);dispatchEvent(new PopStateEvent("popstate"))}',
        "/runs/" + partial.id + "/journey",
    )
    expect(page.get_by_text("This record has visibility limits")).to_be_visible()
    expect(page.get_by_text("BODY_UNAVAILABLE", exact=True)).to_be_visible()
    page.route(
        "**/api/v1/runs?*",
        lambda route: route.fulfill(
            status=200, json={"items": [], "total": 0, "limit": 50, "offset": 0, "demo": False}
        ),
    )
    page.get_by_role("link", name="Changes").click()
    expect(page.get_by_text("Choose two recorded visits")).to_be_visible()
    page.route(
        "**/api/v1/comparisons?*",
        lambda route: route.fulfill(
            status=503,
            json={"error": {"code": "UNAVAILABLE", "message": "Synthetic failure; " + ("long " * 100)}},
        ),
    )
    page.evaluate(
        "history.pushState(null,'','/changes?baseline="
        + ("a" * 32)
        + "&candidate="
        + ("b" * 32)
        + "');dispatchEvent(new PopStateEvent('popstate'))"
    )
    expect(page.get_by_text("Local records unavailable")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_T31_hostile_evidence_is_text(workbench):
    page, _, b, _, _ = workbench
    attempts = []
    page.on("dialog", lambda dialog: attempts.append(dialog.message))
    page.evaluate(
        '(id)=>{history.pushState(null,"","/evidence/"+id);dispatchEvent(new PopStateEvent("popstate"))}',
        b.evidence[0].id,
    )
    page.get_by_text("Sanitized record preview", exact=True).click()
    expect(page.locator("pre")).to_contain_text("<img src=x onerror=alert(1)>")
    assert attempts == []
    assert page.locator("iframe,object,embed").count() == 0
    assert page.evaluate("localStorage.length+sessionStorage.length") == 0


def test_T32_mobile_evidence_back_preserves_comparison(workbench):
    page, a, b, mismatch, _ = workbench
    page.set_viewport_size({"width": 390, "height": 844})
    path = "/changes?baseline=" + a.id + "&candidate=" + b.id + "&filter=ADDED"
    page.evaluate(
        '(path)=>{history.pushState(null,"",path);dispatchEvent(new PopStateEvent("popstate"))}', path
    )
    expect(page.locator(".change-row")).to_have_count(1)
    page.locator(".change-row").click()
    expect(page.get_by_role("heading", name="Evidence", exact=True)).to_be_visible()
    page.get_by_role("button", name="Back to comparison", exact=True).click()
    expect(page.get_by_role("button", name="ADDED", exact=True)).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".change-row")).to_have_attribute("aria-pressed", "true")
    page.get_by_label("Candidate", exact=True).select_option(mismatch.id)
    expect(page.get_by_text("These visits are not comparable")).to_be_visible()


def test_T33_fixture_labelled_screenshots(workbench, root):
    page, a, b, mismatch, partial = workbench
    out = root / "reports/screenshots"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        for name, path in [
            ("assessments", "/assessments"),
            ("journey", "/runs/" + b.id + "/journey"),
            ("changes", "/changes?baseline=" + a.id + "&candidate=" + b.id),
            ("evidence", "/evidence/" + b.evidence[0].id),
            ("partial", "/runs/" + partial.id + "/journey"),
            ("incompatible", "/changes?baseline=" + a.id + "&candidate=" + mismatch.id),
            ("missing-body", "/evidence/" + partial.evidence[0].id),
        ]:
            page.evaluate(
                '(path)=>{history.pushState(null,"",path);dispatchEvent(new PopStateEvent("popstate"))}', path
            )
            heading = {"partial": "Journey", "incompatible": "Changes", "missing-body": "Evidence"}.get(
                name, name.capitalize()
            )
            expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
            expect(page.get_by_text("Loading local records…")).to_have_count(0)
            if name == "journey":
                page.locator(".stage-list button").filter(has_text="Checkout").click()
                expect(page.get_by_text("No evidence linked to this step.")).to_have_count(0)
            if name == "changes" and width >= 768:
                page.locator(".change-row").first.click()
                expect(page.locator(".evidence-panel")).to_contain_text("checkout.js")
            file = out / f"{name}-{width}.png"
            page.screenshot(path=str(file), full_page=True)
            manifest.append(
                {
                    "file": file.relative_to(root).as_posix(),
                    "fixture": "Authored synthetic UI records including profile/body/partial variants, DECLARED_IMPORT",
                    "viewport": [width, height],
                    "source_snapshot": source_snapshot(root),
                    "caption": "SYNTHETIC FIXTURE SCREENSHOT",
                    "visual_review": "PENDING_HUMAN_OR_AGENT_IMAGE_INSPECTION",
                }
            )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
