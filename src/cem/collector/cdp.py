"""Direct same-session Chromium evidence. Never refetches response bodies."""

import asyncio
import base64
import hashlib
from urllib.parse import urlsplit
from ..domain import Run, Evidence, FrameRecord
from ..privacy import safe_url, headers, identity, safe_text


class Capture:
    def __init__(self, run: Run, key: bytes, *, url_sanitizer=safe_url, primary_origin=None):
        self.run, self.key = run, key
        self.safe_url = url_sanitizer
        self.primary_origins = (
            (primary_origin,)
            if primary_origin
            else ("http://shop.cem.test:8765", "https://shop.cem.test:8765")
        )
        self.step_id = "initial"
        self.state = "catalog"
        self.pending = {}
        self.queue = asyncio.Queue(maxsize=64)
        self.session = None
        self.worker = None
        self.main_frame = ""
        self.resource_index = {}

    def limit(self, code):
        if code not in self.run.limitation_codes and len(self.run.limitation_codes) < 50:
            self.run.limitation_codes.append(code)

    def state_for(self, url):
        if self.run.fixture_id == "PILOT":
            return self.state
        path = urlsplit(url).path
        return path.strip("/") if path in ("/cart", "/checkout", "/catalog") else self.state

    async def attach(self, context, page):
        self.session = await context.new_cdp_session(page)
        await self.session.send(
            "Network.enable",
            {"maxTotalBufferSize": 16777216, "maxResourceBufferSize": 2097152, "maxPostDataSize": 0},
        )
        await self.session.send("Network.setCacheDisabled", {"cacheDisabled": True})
        await self.session.send("Page.enable")
        tree = await self.session.send("Page.getFrameTree")
        self.main_frame = tree["frameTree"]["frame"]["id"]
        self.session.on("Network.requestWillBeSent", self.request)
        self.session.on("Network.responseReceived", self.response)
        self.session.on("Network.dataReceived", self.data)
        self.session.on("Network.loadingFinished", self.finished)
        self.session.on("Network.loadingFailed", self.failed)
        self.worker = asyncio.create_task(self.capture_bodies())

    def request(self, event):
        self.run.event_count += 1
        if len(self.run.evidence) >= self.run.profile.budgets.events:
            self.limit("EVENT_CAP")
            return
        r = event["request"]
        url = r["url"]
        display, origin = self.safe_url(url)
        kind = (
            "SCRIPT"
            if event.get("type") == "Script"
            else ("DOCUMENT" if event.get("type") == "Document" else "REQUEST")
        )
        frame = "main" if event.get("frameId") == self.main_frame else "unresolved-frame"
        if frame != "main":
            self.limit("FRAME_NETWORK_ATTRIBUTION_PARTIAL")
        state = self.state_for(url)
        ident = identity(url, frame, state, self.key) if frame == "main" else ""
        e = Evidence(
            kind=kind,
            step_id=self.step_id,
            state=state,
            frame_id=frame,
            origin=origin,
            url_display=display,
            identity=ident,
            request_observed=True,
            method=safe_text(r.get("method", "GET"), 12),
            delivery="ATTEMPTED",
            relation="SAME_ORIGIN" if origin in self.primary_origins else "CROSS_ORIGIN",
        )
        if event.get("redirectResponse"):
            # Redirect destination still passes the route allowlist. Store only sanitized predecessor.
            old = self.pending.get(event["requestId"])
            if old:
                e.redirected_from = old["e"].url_display
        self.run.evidence.append(e)
        self.pending[event["requestId"]] = {"e": e, "length": 0, "seen_length": False, "completed": False}
        if ident:
            self.resource_index[(ident, kind)] = e
        # No request headers, postData or raw URL retained here.

    def response(self, event):
        item = self.pending.get(event["requestId"])
        if not item:
            return
        r = event["response"]
        e = item["e"]
        e.response_observed = True
        status = int(r.get("status", 200))
        e.http_status = status if 100 <= status <= 599 else None
        e.headers = headers(r.get("headers", {}))
        e.content_type = safe_text(r.get("mimeType", ""), 120)
        e.content_encoding = safe_text(e.headers.get("content-encoding", ""), 80)
        e.from_cache = bool(r.get("fromDiskCache") or r.get("fromPrefetchCache"))
        e.from_service_worker = bool(r.get("fromServiceWorker"))
        e.delivery = "RESPONSE_OBSERVED"
        e.tls_validation = (
            "VALIDATED"
            if e.url_display.startswith("https://") and r.get("securityDetails")
            else ("NOT_APPLICABLE" if e.url_display.startswith("http://") else "UNKNOWN")
        )
        if e.from_service_worker:
            self.limit("SERVICE_WORKER_VISIBILITY_PARTIAL")
        if event.get("type") == "Script":
            e.kind = "SCRIPT"

    def data(self, event):
        item = self.pending.get(event["requestId"])
        if item:
            item["seen_length"] = True
            item["length"] += max(0, int(event.get("dataLength", 0)))
            if item["length"] > self.run.profile.budgets.body_bytes:
                item["e"].body_reason = "BODY_OVERSIZED"
                self.limit("BODY_CAP")

    def finished(self, event):
        item = self.pending.get(event["requestId"])
        if not item:
            return
        item["completed"] = True
        if item["e"].kind != "SCRIPT":
            return
        try:
            self.queue.put_nowait((event["requestId"], item))
        except asyncio.QueueFull:
            item["e"].body_reason = "BODY_QUEUE_CAP"
            self.limit("BODY_QUEUE_CAP")

    def failed(self, event):
        item = self.pending.get(event["requestId"])
        if item:
            item["e"].delivery = "FAILED"
            item["e"].body_reason = "REQUEST_FAILED"
            item["e"].limitation_codes.append("REQUEST_FAILED")
            if event.get("blockedReason"):
                self.limit("BROWSER_BLOCKED_REQUEST")

    async def capture_bodies(self):
        while True:
            request_id, item = await self.queue.get()
            try:
                e = item["e"]
                if not item["completed"] or not item["seen_length"]:
                    e.body_reason = "BODY_SIZE_UNKNOWN"
                elif item["length"] > self.run.profile.budgets.body_bytes:
                    e.body_reason = "BODY_OVERSIZED"
                else:
                    try:
                        # Exactly one request to the existing session. No Network.loadNetworkResource.
                        result = await asyncio.wait_for(
                            self.session.send("Network.getResponseBody", {"requestId": request_id}), timeout=5
                        )
                        encoded = result["body"]
                        if len(encoded) > self.run.profile.budgets.body_bytes * 2:
                            e.body_reason = "BODY_OVERSIZED"
                            self.limit("BODY_CAP")
                            continue
                        raw = (
                            base64.b64decode(encoded, validate=True)
                            if result.get("base64Encoded")
                            else encoded.encode("utf-8")
                        )
                        if len(raw) > self.run.profile.budgets.body_bytes:
                            e.body_reason = "BODY_OVERSIZED"
                            self.limit("BODY_CAP")
                        else:
                            e.body_size = len(raw)
                            e.body_representation = (
                                "CDP_BASE64_DECODED"
                                if result.get("base64Encoded")
                                else "CDP_TEXT_UTF8_REENCODED"
                            )
                            e.body_sha256 = hashlib.sha256(raw).hexdigest()
                            e.body_reason = None
                        del raw, result, encoded
                    except (Exception, asyncio.TimeoutError):
                        e.body_reason = "BODY_UNAVAILABLE_NO_REFETCH"
            finally:
                self.queue.task_done()

    async def dom_inventory(self, page):
        for i, frame in enumerate(page.frames[:100]):
            fid = "main" if i == 0 else f"frame-{i}"
            _, origin = self.safe_url(frame.url)
            if not any(f.id == fid for f in self.run.frames):
                self.run.frames.append(
                    FrameRecord(
                        id=fid,
                        origin=origin,
                        parent_id=None if i == 0 else "main",
                        visibility="NETWORK" if i == 0 else "PARTIAL",
                    )
                )
            if i > 0:
                self.limit("FRAME_BODY_VISIBILITY_PARTIAL")
            try:
                # Fixed metadata-only instrumentation, not operator-provided executable configuration.
                refs = await frame.evaluate(
                    """(cap) => Array.from(document.scripts).slice(0,cap).map(s=>({
                    src:s.src, integrity:(s.getAttribute('integrity')||'').slice(0,512),
                    external:!!s.src, type:(s.type||'').slice(0,80)}))""",
                    self.run.profile.budgets.events,
                )
                for ref in refs:
                    if len(self.run.evidence) >= self.run.profile.budgets.events:
                        self.limit("EVENT_CAP")
                        break
                    url = ref["src"]
                    ident = identity(url, fid, self.state, self.key) if ref["external"] else ""
                    found = self.resource_index.get((ident, "SCRIPT"))
                    if found:
                        found.reference_observed = True
                        found.integrity_metadata = safe_text(ref["integrity"], 512) or None
                        continue
                    display, ref_origin = self.safe_url(url) if url else ("", origin)
                    e = Evidence(
                        kind="SCRIPT" if ref["external"] else "INLINE_METADATA",
                        step_id=self.step_id,
                        state=self.state,
                        frame_id=fid,
                        origin=ref_origin,
                        url_display=display,
                        identity=ident,
                        reference_observed=True,
                        integrity_metadata=safe_text(ref["integrity"], 512) or None,
                        body_reason="REFERENCE_ONLY_NO_BODY",
                        content_type=safe_text(ref["type"], 80),
                        relation="SAME_ORIGIN" if ref_origin == origin else "CROSS_ORIGIN",
                    )
                    self.run.evidence.append(e)
                    if ident:
                        self.resource_index[(ident, e.kind)] = e
            except Exception:
                self.limit("DOM_METADATA_UNAVAILABLE")

    async def close(self):
        if self.worker:
            try:
                await asyncio.wait_for(self.queue.join(), timeout=10)
            except asyncio.TimeoutError:
                self.limit("BODY_DRAIN_TIMEOUT")
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        if self.session:
            try:
                await self.session.detach()
            except Exception:
                self.limit("CDP_DETACH_ERROR")
