"""Container-only entry: verifies namespace assumptions, starts synthetic fixtures, writes bounded output."""

import asyncio
import os
import socket
import subprocess
import signal
from pathlib import Path
from cem.config import load_job
from cem.authorization import validate_job
from cem.domain import MAX_IMPORT
from cem.privacy import sanitize_run
from cem.collector.journey import collect
from cem.collector.http_only import collect_http
from fixtures.server import Fixtures


def main():
    if os.geteuid() == 0 or os.environ.get("CEM_ISOLATED_JOB") != "1":
        raise SystemExit("ISOLATION_UNAVAILABLE")
    if {name for _, name in socket.if_nameindex()} != {"lo"}:
        raise SystemExit("ISOLATION_UNAVAILABLE: loopback-only namespace required")
    if any(
        os.environ.get(n)
        for n in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    ):
        raise SystemExit("ISOLATION_UNAVAILABLE: proxy settings forbidden")
    job = load_job(Path("/job/job.json"))
    validate_job(job)
    key = Path("/job/identity-key").read_bytes()
    if len(key) != 32:
        raise SystemExit("KEY_INVALID")
    home = Path("/tmp/cem-home")
    home.mkdir(mode=0o700, exist_ok=True)
    nss = home / ".pki/nssdb"
    nss.mkdir(parents=True, mode=0o700, exist_ok=True)
    # This trusts the synthetic CA only inside this disposable container home.
    subprocess.run(
        ["certutil", "-N", "--empty-password", "-d", "sql:" + str(nss)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "certutil",
            "-A",
            "-d",
            "sql:" + str(nss),
            "-n",
            "CEM synthetic CA",
            "-t",
            "C,,",
            "-i",
            "/opt/cem/lab/certs/ca.crt",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["HOME"] = str(home)
    scheme = "https" if all(o.startswith("https:") for o in job.grant.origins) else "http"
    # T15 keeps an HTTP attempted origin in the grant; fixture listener remains HTTPS.
    if job.grant.fixture_id == "T15":
        scheme = "https"
    fixtures = Fixtures(job.grant.fixture_id, Path("/opt/cem/lab/certs"), scheme)
    fixtures.start()
    try:
        if job.arm == "HTTP":
            run = collect_http(job, key, Path("/opt/cem/lab/certs/ca.crt"))
        else:

            async def supervised():
                task = asyncio.create_task(collect(job, key))
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, task.cancel)
                return await task

            run = asyncio.run(supervised())
        run = sanitize_run(run)
        raw = run.model_dump_json(indent=2).encode()
        if len(raw) > MAX_IMPORT:
            raise SystemExit("ARTIFACT_LIMIT")
        temporary = Path("/output/run.pending")
        temporary.write_bytes(raw)
        os.replace(temporary, Path("/output/run.json"))
    finally:
        fixtures.close()


if __name__ == "__main__":
    main()
