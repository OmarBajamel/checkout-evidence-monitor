"""Fixed container entrypoint. No operator-supplied executable paths."""

import asyncio
import ipaddress
import json
import os
from pathlib import Path
import sys
import time
from .policy import PilotConfig, require_grant
from ..storage import validate_id


def main():
    if os.getuid() != 1000 or os.environ.get("CEM_PILOT_CONTAINER") != "1":
        raise SystemExit(3)
    raw = Path("/job/config.json").read_bytes()
    if len(raw) > 8192:
        raise SystemExit(3)
    config = PilotConfig.model_validate_json(raw)
    require_grant(config)
    token = Path("/job/proxy-token").read_text().strip()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise SystemExit(3)
    if sys.argv[1:] == ["proxy"]:
        from .proxy import serve

        asyncio.run(serve(config, token))
    elif sys.argv[1:] == ["browser"]:
        from .collector import collect

        proxy = str(ipaddress.IPv4Address(os.environ["CEM_PROXY_IP"]))
        key = Path("/job/identity-key").read_bytes()
        if len(key) != 32:
            raise SystemExit(3)
        run_id = validate_id(os.environ["CEM_RUN_ID"])
        run = asyncio.run(collect(config, key, run_id, proxy, token))
        raw = run.model_dump_json().encode()
        if len(raw) > 50 * 1024 * 1024:
            raise SystemExit(3)
        Path("/output/run.json").write_bytes(raw)
        Path("/output/status.json").write_text(json.dumps({"status": run.status}))
        # Keep bounded tmpfs alive for the host-controlled transfer; browser context is already closed.
        time.sleep(60)
    else:
        raise SystemExit(3)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # No traceback can leak private configuration, page data, or credentials.
        raise SystemExit(3) from None
