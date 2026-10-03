"""Navigation-only public pilot; called only inside the inspected browser container."""

import asyncio
import hashlib
import time
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
from .policy import PilotConfig, require_grant, allow_request, display_url
from ..collector.cdp import Capture
from ..domain import Run, Profile, StepResult, CookieRecord, utc_now
from ..errors import CEMError
from ..privacy import identity, sanitize_run


def make_run(config: PilotConfig, key: bytes, run_id: str) -> Run:
    return Run(
        id=run_id,
        label=config.label,
        fixture_id="PILOT",
        provenance="COLLECTED_PILOT",
        journey=config.steps,
        profile=Profile(
            target_id=config.target_id,
            fixture_version="public-pilot-1",
            authentication="PUBLIC_GUEST",
            journey_hash=config.fingerprint(),
            identity_key_id=hashlib.sha256(key).hexdigest()[:16],
            consent="UNSET",
            budgets=config.budgets,
            collector_version="cem-pilot-1",
        ),
    )


async def collect(config: PilotConfig, key: bytes, run_id: str, proxy_ip: str, token: str) -> Run:
    require_grant(config)
    run = make_run(config, key, run_id)
    capture = Capture(
        run, key, url_sanitizer=lambda u: display_url(u, config.grant.origins), primary_origin=config.origin
    )
    start = time.monotonic()
    browser = context = None
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                chromium_sandbox=True,
                proxy={"server": f"http://{proxy_ip}:8888", "username": "cem", "password": token},
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--no-first-run",
                    "--disable-default-apps",
                    "--disable-quic",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                ],
            )
            if browser.version != run.profile.browser_version:
                raise CEMError("BROWSER_VERSION_MISMATCH", "The pinned browser version differs.")
            context = await browser.new_context(
                service_workers="block",
                ignore_https_errors=False,
                accept_downloads=False,
                viewport={"width": 1440, "height": 900},
                locale="en-US",
            )
            redirects = 0

            async def route(route, request):
                nonlocal redirects
                try:
                    allow_request(
                        config, request.url, request.method, navigation=request.is_navigation_request()
                    )
                    if request.redirected_from:
                        redirects += 1
                    if redirects > config.budgets.redirects or run.event_count >= config.budgets.events:
                        raise CEMError("REQUEST_CAP", "Request budget reached.")
                    await route.continue_()
                except CEMError as exc:
                    capture.limit(exc.code)
                    await route.abort("blockedbyclient")

            async def websocket(ws):
                capture.limit("WEBSOCKET_DENIED")
                await ws.close()

            await context.route("**/*", route)
            await context.route_web_socket("**/*", websocket)
            page = await context.new_page()

            async def popup(other):
                if other != page:
                    capture.limit("POPUP_DENIED")
                    await other.close()

            context.on("page", popup)
            context.on("requestfailed", lambda _: capture.limit("PILOT_REQUEST_FAILED"))
            page.on("download", lambda download: asyncio.create_task(download.cancel()))
            await capture.attach(context, page)
            async with asyncio.timeout(config.budgets.run_seconds):
                for step in config.steps:
                    require_grant(config)
                    capture.step_id, capture.state = step.id, step.expected_state
                    redirects = 0
                    began = utc_now()
                    try:
                        if step.action == "stop":
                            pass
                        elif step.action == "goto":
                            response = await page.goto(
                                config.origin + step.path,
                                wait_until="domcontentloaded",
                                timeout=config.budgets.step_seconds * 1000,
                            )
                            if response is None or response.status >= 400:
                                raise CEMError(
                                    "NAVIGATION_FAILED", "A declared page did not return a usable response."
                                )
                        if step.selector:
                            await page.locator(step.selector).wait_for(
                                state="visible", timeout=config.budgets.step_seconds * 1000
                            )
                        if step.action != "stop":
                            await asyncio.sleep(0.8)
                            await capture.dom_inventory(page)
                            run.complete_states.append(step.expected_state)
                        run.steps.append(
                            StepResult(
                                id=step.id,
                                state=step.expected_state,
                                status="REACHED",
                                started_at=began,
                                ended_at=utc_now(),
                            )
                        )
                        if step.action == "stop":
                            break
                    except (BrowserTimeout, CEMError) as exc:
                        code = exc.code if isinstance(exc, CEMError) else "STEP_TIMEOUT"
                        capture.limit(code)
                        run.steps.append(
                            StepResult(
                                id=step.id,
                                state=step.expected_state,
                                status="BLOCKED",
                                reason=code,
                                started_at=began,
                                ended_at=utc_now(),
                            )
                        )
                        break
                for cookie in (await context.cookies())[:100]:
                    run.cookies.append(
                        CookieRecord(
                            name="cookie-" + identity(cookie["name"], cookie["domain"], "cookie", key)[:24],
                            domain=cookie["domain"],
                            path="/[redacted-path]",
                            secure=cookie["secure"],
                            http_only=cookie["httpOnly"],
                            same_site=cookie["sameSite"],
                        )
                    )
                run.status = "PARTIAL" if run.limitation_codes else "COMPLETED"
        except asyncio.CancelledError:
            run.status = "CANCELLED"
            capture.limit("CANCELLED")
        except TimeoutError:
            run.status = "PARTIAL"
            capture.limit("RUN_TIMEOUT")
        except CEMError as exc:
            run.status = "FAILED"
            capture.limit(exc.code)
        except Exception:
            run.status = "FAILED"
            capture.limit("COLLECTOR_ERROR")
        finally:
            for close in [
                capture.close,
                *([context.close] if context else []),
                *([browser.close] if browser else []),
            ]:
                try:
                    await asyncio.wait_for(close(), 5)
                except (Exception, asyncio.CancelledError):
                    capture.limit("CLEANUP_UNCONFIRMED")
            reached = {s.id for s in run.steps}
            for step in config.steps:
                if step.id not in reached:
                    run.steps.append(
                        StepResult(
                            id=step.id,
                            state=step.expected_state,
                            status="NOT_RUN",
                            reason="PREVIOUS_STEP_BLOCKED",
                            started_at=utc_now(),
                            ended_at=utc_now(),
                        )
                    )
            run.ended_at = utc_now()
            run.elapsed_ms = int((time.monotonic() - start) * 1000)
            if run.limitation_codes:
                run.complete_states = []
                if run.status == "COMPLETED":
                    run.status = "PARTIAL"
    return sanitize_run(run, pilot_origins=config.grant.origins)
