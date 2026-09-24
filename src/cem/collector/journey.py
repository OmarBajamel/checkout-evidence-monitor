"""Bounded synthetic observation. Must be launched through the inspected LAB wrapper."""

import asyncio
import hashlib
import json
import time
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
from ..domain import Job, Run, Profile, StepResult, CookieRecord, utc_now, RunStatus
from ..authorization import validate_job, allow_request
from ..errors import CEMError
from ..privacy import safe_text
from .cdp import Capture


def make_run(job: Job, key: bytes) -> Run:
    profile = Profile(
        journey_hash=hashlib.sha256(
            json.dumps([s.model_dump() for s in job.steps], sort_keys=True).encode()
        ).hexdigest(),
        identity_key_id=hashlib.sha256(key).hexdigest()[:16],
        consent=job.consent,
        service_workers=job.service_workers,
        budgets=job.budgets,
        mode=job.arm,
    )
    return Run(
        label=f"{job.grant.fixture_id} · {job.arm}",
        fixture_id=job.grant.fixture_id,
        profile=profile,
        grant=job.grant,
        journey=job.steps,
        provenance="COLLECTED_LAB",
    )


async def collect(job: Job, key: bytes) -> Run:
    validate_job(job)
    run = make_run(job, key)
    capture = Capture(run, key)
    start = time.monotonic()
    browser = None
    context = None
    base = next((x for x in job.grant.origins if "shop.cem.test" in x), None)
    if not base:
        raise CEMError("SCOPE_DENIED", "A storefront origin is required.")
    redirects = 0
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                chromium_sandbox=True,
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--no-first-run",
                    "--disable-default-apps",
                ],
            )
            if browser.version != run.profile.browser_version:
                raise CEMError(
                    "BROWSER_VERSION_MISMATCH",
                    "Browser version does not match the selected observation profile.",
                )
            context = await browser.new_context(
                service_workers=job.service_workers,
                ignore_https_errors=False,
                viewport={"width": run.profile.viewport[0], "height": run.profile.viewport[1]},
                locale=run.profile.locale,
                accept_downloads=False,
            )

            async def route_handler(route, request):
                nonlocal redirects
                try:
                    validate_job(job)
                    allow_request(request.url, request.method, job.grant.origins)
                    if request.redirected_from:
                        redirects += 1
                        if redirects > job.budgets.redirects:
                            raise CEMError("REDIRECT_CAP", "Redirect cap reached.")
                    if run.event_count >= job.budgets.events:
                        raise CEMError("EVENT_CAP", "Event cap reached.")
                    await route.continue_()
                except CEMError as error:
                    capture.limit(error.code)
                    await route.abort("blockedbyclient")

            await context.route("**/*", route_handler)
            page = await context.new_page()

            async def deny_new_page(new_page):
                if new_page != page:
                    capture.limit("POPUP_DENIED")
                    await new_page.close()

            context.on("page", deny_new_page)
            page.on("download", lambda download: asyncio.create_task(download.cancel()))
            await capture.attach(context, page)
            if job.service_workers == "allow":
                capture.limit("SERVICE_WORKER_VISIBILITY_PARTIAL")
            async with asyncio.timeout(job.budgets.run_seconds):
                steps = job.steps if job.arm == "JOURNEY" else job.steps[:1]
                for step in steps:
                    validate_job(job)
                    redirects = 0
                    capture.step_id = step.id
                    t = utc_now()
                    expected = step.expected_state or capture.state
                    if step.expected_state and step.expected_state != "stopped":
                        capture.state = step.expected_state
                    try:
                        if step.action == "goto":
                            url = base + (step.path or "/") + f"?scenario={job.grant.fixture_id}"
                            allow_request(url, "GET", job.grant.origins)
                            await page.goto(
                                url, wait_until="domcontentloaded", timeout=job.budgets.step_seconds * 1000
                            )
                        elif step.action == "stop":
                            run.steps.append(
                                StepResult(
                                    id=step.id,
                                    state="stopped",
                                    status="REACHED",
                                    started_at=t,
                                    ended_at=utc_now(),
                                )
                            )
                            break
                        elif step.action in ("wait", "assert"):
                            await page.locator(step.selector).wait_for(
                                state="visible", timeout=job.budgets.step_seconds * 1000
                            )
                        else:
                            loc = page.locator(step.selector)
                            if await loc.count() != 1:
                                raise CEMError(
                                    "SELECTOR_NOT_UNIQUE", "Exactly one declared action target is required."
                                )
                            if step.action == "click":
                                await loc.click(timeout=job.budgets.step_seconds * 1000)
                            elif step.action == "fill":
                                await loc.fill(step.value, timeout=job.budgets.step_seconds * 1000)
                            elif step.action == "select":
                                await loc.select_option(step.value, timeout=job.budgets.step_seconds * 1000)
                        if step.expected_state and step.expected_state != "stopped":
                            await page.locator(f"[data-state='{step.expected_state}']").wait_for(
                                state="visible", timeout=job.budgets.step_seconds * 1000
                            )
                        # Fixed bounded observation window, not a claim of network idleness/completeness.
                        await asyncio.sleep(min(0.8, job.budgets.step_seconds))
                        await capture.dom_inventory(page)
                        run.steps.append(
                            StepResult(
                                id=step.id, state=expected, status="REACHED", started_at=t, ended_at=utc_now()
                            )
                        )
                        if not run.limitation_codes and expected not in run.complete_states:
                            run.complete_states.append(expected)
                    except (BrowserTimeout, CEMError) as error:
                        code = error.code if isinstance(error, CEMError) else "STEP_TIMEOUT"
                        capture.limit(code)
                        run.steps.append(
                            StepResult(
                                id=step.id,
                                state=expected,
                                status="BLOCKED",
                                reason=code,
                                started_at=t,
                                ended_at=utc_now(),
                            )
                        )
                        break
                seen = {s.id for s in run.steps}
                for step in job.steps:
                    if step.id not in seen:
                        run.steps.append(
                            StepResult(
                                id=step.id,
                                state=step.expected_state or "unknown",
                                status="NOT_RUN",
                                reason="ARM_HAS_NO_JOURNEY"
                                if job.arm != "JOURNEY"
                                else "PREVIOUS_STEP_BLOCKED",
                                started_at=utc_now(),
                                ended_at=utc_now(),
                            )
                        )
                for cookie in (await context.cookies())[:100]:
                    run.cookies.append(
                        CookieRecord(
                            name=safe_text(cookie["name"], 80),
                            domain=cookie["domain"],
                            path=cookie["path"],
                            secure=cookie["secure"],
                            http_only=cookie["httpOnly"],
                            same_site=cookie["sameSite"],
                            role="CONFIGURED_SESSION" if cookie["name"] == "cem-session" else "UNKNOWN",
                        )
                    )
                run.status = (
                    RunStatus.PARTIAL
                    if run.limitation_codes or any(s.status == "BLOCKED" for s in run.steps)
                    else RunStatus.COMPLETED
                )
        except asyncio.CancelledError:
            run.status = RunStatus.CANCELLED
            capture.limit("CANCELLED")
        except TimeoutError:
            run.status = RunStatus.PARTIAL
            capture.limit("RUN_TIMEOUT")
        except CEMError as error:
            run.status = RunStatus.FAILED
            capture.limit(error.code)
        except Exception:
            run.status = RunStatus.FAILED
            capture.limit("COLLECTOR_ERROR")
        finally:
            for close in [
                capture.close,
                *([context.close] if context else []),
                *([browser.close] if browser else []),
            ]:
                try:
                    await asyncio.wait_for(close(), timeout=5)
                except (Exception, asyncio.CancelledError):
                    capture.limit("CLEANUP_UNCONFIRMED")
            run.ended_at = utc_now()
            run.elapsed_ms = int((time.monotonic() - start) * 1000)
            if run.limitation_codes:
                run.complete_states = []
                if run.status == RunStatus.COMPLETED:
                    run.status = RunStatus.PARTIAL
    return run
