"""Authenticated bounded CONNECT relay. No TLS interception and no request logging."""

import asyncio
import base64
from datetime import datetime, timezone
import hmac
import ipaddress
import socket
from .policy import PilotConfig, require_grant, public_address
from ..errors import CEMError


async def resolve_public(host: str) -> list[tuple]:
    answers = await asyncio.wait_for(
        asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP),
        8,
    )
    if not answers or any(not public_address(a[4][0]) for a in answers):
        raise CEMError("EGRESS_DENIED", "Destination did not resolve exclusively to public addresses.")
    return sorted(answers, key=lambda a: a[0] != socket.AF_INET)


class Relay:
    def __init__(self, config: PilotConfig, token: str):
        self.config = config
        self.auth = "Basic " + base64.b64encode(("cem:" + token).encode()).decode()
        self.hosts = {o.removeprefix("https://") for o in config.grant.origins}
        self.active = 0
        self.requests = 0
        self.bytes = 0
        self.deadline = asyncio.get_running_loop().time() + min(
            config.budgets.run_seconds + 20,
            max(0, (config.grant.expires_at - datetime.now(timezone.utc)).total_seconds()),
        )
        self.max_bytes = 50 * 1024 * 1024

    async def pipe(self, reader, writer):
        while True:
            data = await reader.read(32768)
            if not data:
                return
            self.bytes += len(data)
            if self.bytes > self.max_bytes:
                raise CEMError("TRANSFER_CAP", "Pilot transfer budget reached.")
            writer.write(data)
            await writer.drain()

    async def handle(self, reader, writer):
        upstream = None
        counted = False
        tasks = []
        try:
            if (
                self.active >= 16
                or self.requests >= self.config.budgets.events
                or self.bytes >= self.max_bytes
            ):
                return
            self.active += 1
            counted = True
            self.requests += 1
            remaining = self.deadline - asyncio.get_running_loop().time()
            async with asyncio.timeout(max(0, remaining)):
                require_grant(self.config)
                raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
                if len(raw) > 8192:
                    return
                lines = raw.decode("ascii", errors="strict").split("\r\n")
                method, authority, protocol = lines[0].split(" ")
                if method != "CONNECT" or protocol != "HTTP/1.1" or authority.count(":") != 1:
                    return
                host, port = authority.split(":")
                if host not in self.hosts or port != "443":
                    return
                fields = {}
                for line in lines[1:]:
                    if not line:
                        continue
                    key, value = line.split(":", 1)
                    key = key.lower()
                    if key in fields or key.strip() != key:
                        return
                    fields[key] = value.strip()
                if not hmac.compare_digest(fields.get("proxy-authorization", ""), self.auth):
                    writer.write(
                        b"HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm=cem\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                    )
                    await writer.drain()
                    return
                if fields.get("transfer-encoding") or fields.get("content-length", "0") != "0":
                    return
                answers = await resolve_public(host)
                # A literal, previously checked address prevents a second DNS resolution on connect.
                address = answers[0][4][0]
                family = socket.AF_INET6 if ipaddress.ip_address(address).version == 6 else socket.AF_INET
                up_reader, upstream = await asyncio.wait_for(
                    asyncio.open_connection(address, 443, family=family), 8
                )
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                tasks = [
                    asyncio.create_task(self.pipe(reader, upstream)),
                    asyncio.create_task(self.pipe(up_reader, writer)),
                ]
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
        except (Exception, asyncio.CancelledError):
            # Never echo target URLs, credentials or arbitrary network error text.
            pass
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for stream in (writer, upstream):
                if stream:
                    stream.close()
                    try:
                        await asyncio.wait_for(stream.wait_closed(), 1)
                    except Exception:
                        pass
            if counted:
                self.active -= 1


async def serve(config: PilotConfig, token: str):
    relay = Relay(config, token)
    server = await asyncio.start_server(relay.handle, "0.0.0.0", 8888, limit=8192)
    async with server:
        await asyncio.sleep(max(0, relay.deadline - asyncio.get_running_loop().time()))
