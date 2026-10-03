# Getting started

[Documentation](README.md) · [العربية](ar/GETTING_STARTED.md)

**0.2.0 alpha:** these are authored setup procedures. A fresh installation and runtime session have not yet been verified for this version. The source builds were checked; that is a different claim.

## Requirements

| Component | Requirement |
|---|---|
| Python | CPython 3.12; use a project-local virtual environment |
| Node.js | 24.x; needed to rebuild the frontend |
| Git | For cloning and source version tracking |
| Browser | A local browser for the loopback workbench |
| Docker | Only for LAB/PILOT collection: local Linux x64 engine; PILOT also requires isolated gateway mode |

Keep the repository on a local writable filesystem. Do not place credentials or customer data inside it. Dependency installation needs access to the package registries; OFFLINE refers to evidence review, not an air-gapped installer.

## 1. Prepare the source

### Windows / PowerShell

```powershell
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.0
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-win.lock
Set-Location frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
Set-Location ..
.venv/Scripts/python -m build --no-isolation
.venv/Scripts/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a0-py3-none-any.whl
```

### Linux / Bash

```bash
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.0
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-linux.lock
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
cd ..
.venv/bin/python -m build --no-isolation
.venv/bin/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a0-py3-none-any.whl
```

These commands install dependencies and build source. They do not start CEM. Installation on other systems is unverified; do not bypass a missing hash or unsupported wheel. Release source ZIP users can extract the archive and begin at the virtual-environment step.

## 2. Explicitly open an OFFLINE demo

Run the following only when you choose to authorize local runtime execution for the prepared source. In the clean public repository, this command records the local operator's intent; it is not signed authorization or permission to visit a store.

PowerShell:

```powershell
.venv/Scripts/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
$env:CEM_TEST_SESSION=(Resolve-Path .cem-private/test-session.json).Path
.venv/Scripts/cem ui --demo
```

Bash:

```bash
.venv/bin/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
export CEM_TEST_SESSION="$PWD/.cem-private/test-session.json"
.venv/bin/cem ui --demo
```

Open the printed loopback bootstrap link within 60 seconds. The link is single-use; do not share it. The demo uses authored synthetic records and a separate read-only store. A source change invalidates the runtime session; stop and renew it deliberately. Stop the server with Ctrl+C.

For an empty, writable local workbench, use the same command without `--demo`. Opening it starts no collector. Target setup saves paused and operational controls require the explicitly started authorized runner.

## 3. Follow a review

In Assessments, choose different baseline and candidate records. Open Changes, inspect a resource on both sides, then follow its Evidence link. Journey explains reached states and missing coverage. Review writes are disabled in the demo; use your own appropriately sanitized records in a writable store for the review/export cycle.

## 4. Collection is separate

- **Synthetic LAB:** follow the [LAB procedure](RUNBOOK.md#isolated-linux-lab). It needs an explicit OFFLINE_AND_LAB session, local Docker and a fresh synthetic grant.
- **Experimental PILOT:** read the [pilot guide](PILOT_QUICKSTART.md) and [security boundary](PILOT_SECURITY.md). It additionally needs explicit boundary acceptance and actual authority for exact origins, actions and a short time window. Do not point it at an unrelated store.
- **Tests:** authorizing the demo does not authorize remote CI. The repository's workflow is manual-only and has independent source/intent inputs.

## Troubleshooting

| Symptom | What to check |
|---|---|
| TEST_APPROVAL_REQUIRED | Use the correct profile, current source and unexpired session; do not edit the guard away |
| Blank or stale browser session | Stop CEM and obtain a fresh bootstrap link; bearer credentials are intentionally memory-only |
| RUNNER_OFFLINE | The regular UI does not start the PILOT worker; consult the separate pilot procedure |
| GRANT_EXPIRED | Stop collection and renew actual scoped authority before renewing configuration |
| PILOT_IMAGE_REQUIRED | The image must match the prepared source; rebuild only within an authorized pilot effort |
| ISOLATION_MISMATCH / CLEANUP_UNCONFIRMED | Stop new work and follow the recovery guide; never disable sandbox/network controls |
| Missing dependency wheel | Check Python/OS/architecture against the exact lock; report the incompatibility without removing hashes |

No support SLA or universal platform compatibility is promised. Include the release, profile, operating system and stable error code in a sanitized report.
