"""Controlled synthetic HTTP(S) storefront. No customer, order or payment backend."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import ssl
import threading
import time
import secrets
import json
from pathlib import Path


class FixtureHandler(BaseHTTPRequestHandler):
    scenario = "T01"
    scheme = "https"
    forbidden_attempts = 0

    def log_message(self, *args):
        return

    def do_POST(self):
        type(self).forbidden_attempts += 1
        self.send_error(405, "Synthetic boundary: submissions are forbidden")

    def do_GET(self):
        p = urlsplit(self.path)
        # These paths have no state-changing behavior, even if directly called.
        if any(x in p.path for x in ("order", "submit", "purchase", "account", "mail")):
            type(self).forbidden_attempts += 1
            self.send_error(403, "Action forbidden")
            return
        scenario = type(self).scenario
        q = parse_qs(p.query)
        if "scenario" in q and q["scenario"][0] != scenario:
            self.send_error(400, "Scenario mismatch")
            return
        status = 200
        content_type = "text/html; charset=utf-8"
        body = b""
        extra_headers = {}
        if p.path == "/canary":
            content_type = "application/json"
            body = json.dumps({"forbidden_attempts": type(self).forbidden_attempts}).encode()
        elif p.path == "/redirect":
            target = {"T17": "http://169.254.169.254/latest/meta-data", "T18": "http://[::1]:8765/"}.get(
                scenario, f"{self.scheme}://pay.cem.test:8766/frame"
            )
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()
            return
        elif p.path == "/sw.js":
            content_type = "application/javascript"
            body = b"self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));self.addEventListener('fetch',e=>{if(new URL(e.request.url).pathname==='/scripts/sw-only.js')e.respondWith(new Response('window.syntheticSW=true',{headers:{'Content-Type':'application/javascript'}}))});"
            extra_headers["Service-Worker-Allowed"] = "/"
        elif p.path.startswith("/scripts/") and p.path.endswith(".js"):
            content_type = "application/javascript"
            if p.path == "/scripts/large.js":
                body = b"/*" + b"x" * (2097152 + 200) + b"*/"
            elif p.path == "/scripts/dynamic.js":
                body = f"window.syntheticVariant='{secrets.token_hex(8)}';".encode()
            elif p.path == "/scripts/delayed.js":
                time.sleep(0.25)
                body = b"window.syntheticDelayed=true;"
            elif p.path == "/scripts/base.js":
                body = (
                    b"window.syntheticBase='changed';"
                    if scenario == "T04"
                    else b"window.syntheticBase='baseline';"
                )
            else:
                body = b"window.syntheticFixture=true;"
        elif p.path == "/frame":
            body = b"""<!doctype html><html><body><p>Mock provider frame. No real payment.</p><script src="/scripts/provider.js"></script></body></html>"""
        elif p.path in ("/", "/catalog", "/cart", "/checkout"):
            state = "catalog" if p.path in ("/", "/catalog") else p.path[1:]
            target = "/redirect" if scenario in ("T12", "T17", "T18") else "/checkout"
            checkout_control = (
                ""
                if scenario == "T06"
                else f'<a data-cem="checkout" href="{target}">Review synthetic checkout</a>'
            )
            scripts = ['<script src="/scripts/base.js"></script>']
            if state == "checkout":
                if scenario != "T05":
                    scripts.append('<script src="/scripts/checkout.js"></script>')
                if scenario == "T02":
                    scripts.append('<script src="/scripts/extra.js"></script>')
                if scenario == "T03":
                    scripts.append(
                        f'<script src="{self.scheme}://pay.cem.test:8766/scripts/provider.js"></script>'
                    )
                if scenario == "T07":
                    scripts.append(
                        "<script>setTimeout(()=>{const s=document.createElement('script');s.src='/scripts/delayed.js';document.head.append(s)},250)</script>"
                    )
                if scenario == "T08":
                    scripts.append('<script src="/scripts/dynamic.js"></script>')
                if scenario == "T10":
                    scripts.append('<script src="/scripts/large.js"></script>')
                if scenario == "T15":
                    scripts.append('<script src="http://pay.cem.test:8766/scripts/provider.js"></script>')
                if scenario == "T16":
                    scripts.append('<script src="/scripts/extra.js?dummy=synthetic-secret"></script>')
                if scenario == "T19":
                    scripts.append(
                        "<script>navigator.serviceWorker.register('/sw.js').then(()=>navigator.serviceWorker.ready).then(()=>{const s=document.createElement('script');s.src='/scripts/sw-only.js';document.head.append(s)}).catch(()=>{})</script>"
                    )
                if scenario == "T20":
                    scripts.append(
                        "<script>setInterval(()=>{const s=document.createElement('script');s.src='/scripts/extra.js';document.head.append(s)},20)</script>"
                    )
            frame = (
                f'<iframe title="Synthetic provider" src="{self.scheme}://pay.cem.test:8766/frame"></iframe>'
                if scenario == "T11" and state == "checkout"
                else ""
            )
            hostile = (
                "<p>&lt;img src=x onerror=alert(1)&gt; =HYPERLINK(&quot;synthetic&quot;)</p>"
                if scenario == "T21"
                else ""
            )
            body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Synthetic CEM {state}</title></head>
<body data-state="{state}"><h1>Synthetic {state}</h1><p>Local fixture; no real transaction.</p>
<a data-cem="cart" href="/cart">Review cart</a>{checkout_control}
<label>Email <input data-cem="email" autocomplete="off" type="email"></label>
<label>Country <select data-cem="country"><option>DE</option></select></label>
<label>Consent <select data-cem="consent"><option>DECLINED</option><option>ACCEPTED</option></select></label>
<button type="button" data-cem="forbidden-order">Forbidden order boundary</button>{frame}{hostile}
{"".join(scripts)}</body></html>""".encode()
        else:
            self.send_error(404, "Unknown fixture resource")
            return
        self.send_response(status)
        if scenario == "T13":
            self.send_header("Content-Security-Policy-Report-Only", "default-src 'self'; script-src 'self'")
        else:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://pay.cem.test:8766 http://pay.cem.test:8766; frame-src https://pay.cem.test:8766",
            )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.scheme == "https":
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        if p.path == "/checkout":
            flags = "; HttpOnly; Secure; SameSite=Lax" if scenario != "T14" else "; SameSite=Lax"
            self.send_header("Set-Cookie", "cem-session=synthetic-only; Path=/" + flags)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra_headers.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class Fixtures:
    def __init__(self, scenario, cert_dir: Path, scheme="https"):
        self.servers = []
        self.threads = []
        handler = type(
            "JobFixture", (FixtureHandler,), {"scenario": scenario, "scheme": scheme, "forbidden_attempts": 0}
        )
        for port in (8765, 8766):
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            server.daemon_threads = True
            if scheme == "https":
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(cert_dir / "fixture.crt", cert_dir / "fixture.key")
                server.socket = ctx.wrap_socket(server.socket, server_side=True)
            self.servers.append(server)

    def start(self):
        for server in self.servers:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            self.threads.append(t)

    def close(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        for t in self.threads:
            t.join(timeout=2)
