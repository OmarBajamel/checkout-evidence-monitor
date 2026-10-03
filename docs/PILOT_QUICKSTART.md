# Guided local pilot — V1.1 / 0.2.0a0
This increment is implemented in source and is awaiting runtime verification. The published v0.1.0 prototype and its September 24 results describe the earlier synthetic-only version.

## 1. Prepare the local workspace
Use Python 3.12 and Node 24. Read [Getting started](GETTING_STARTED.md) for hash-locked Windows/Linux dependency preparation, frontend build and wheel installation. Keep the project in its own writable directory. The UI and evidence store are local; no account, merchant API or paid service is needed. For collection, use a local Linux x64 Docker engine supporting internal bridge gateway mode isolated. A remote Docker context is refused.

## 2. Open the evidence workbench
After a new explicit runtime approval for the current source, record it using the original runbook's authorization procedure. An OFFLINE session can open the application and configure targets; it cannot operate the pilot browser.
Run cem ui explicitly and open the one-time loopback bootstrap link within 60 seconds. The bearer remains in memory; restarting creates a fresh link. Do not share it. For the synthetic dataset use cem ui --demo; writes are disabled.
Opening the regular workbench starts no collector or worker.

## 3. Configure a supported store
Assessments → Monitoring → Set up store.
Provide a stable lowercase target ID, readable name, HTTPS origin and authorizing operator.
Define at most 12 steps: page visit, visible-element wait/check, or stop. Navigation requires an exact public path with no query and a CSS selector that identifies the intended visible state. Name the state catalog, cart or checkout entry. Stop before any transaction.
Add only resource origins within your authorization, including necessary CDNs. Unlisted resource requests are blocked and may make a visit partial. No wildcards, credentials, IP literals, alternate ports, authenticated session or form input is accepted. HTTP methods are GET/HEAD only. Consent stays unset.
Choose a 15-minute-or-longer cadence and a grant of 1–8 hours. Review the exact pages/origins and authority attestation. Save paused. Nothing visits the store at this point.

## 4. Prepare the explicitly authorized pilot runtime
This step needs the new pilot boundary to be accepted and a separately authorized named store/staging scope. The prior LAB-only chroot/network permission does not authorize PILOT operation.
After that approval, the operator may run these commands from the project root:
```powershell
.venv/Scripts/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile PILOT --pilot-boundary-accepted
$env:CEM_TEST_SESSION=(Resolve-Path .cem-private/test-session.json).Path
$env:PYTHONPATH='src'
.venv/Scripts/python tools/build_pilot.py
.venv/Scripts/cem ui --monitor
```
On Linux use .venv/bin paths and shell export assignments; run as a non-root operator.
Build the frontend before authorizing, because the session and image are bound to all source/build bytes. Image preparation downloads exact hash-locked Linux wheels and the digest-pinned base; it starts no container. Changing source invalidates the session/image.
The --monitor option explicitly starts the local worker and resumes previously enabled, unexpired cadences. It is an operational choice. No grant means no collection.

## 5. Complete a review cycle
Choose Run once. Inspect its Journey, visible-state evidence, provenance and limitations.
In Recorded visits select that record, choose Select saved baseline, enter a reason and confirm. A baseline is a reference, not a safety approval.
Start cadence only for the period you authorized. Keep the runner active. Later records appear in Assessments and actionable outcomes in Inbox. A difference, partial result, failed observation, expired grant or missed cadence has a visible explanation.
Open a comparison, inspect both sides, follow evidence, and record Expected / Investigate / Deferred / Reviewed with a reason. Export review downloads the sanitized pair, integrity/profile context and full retained decision history. Existing HTML/JSON/CSV run exports remain available.

## 6. Stop, renew and retain
Pause cancels queued work and requests termination of the active visit. Cancellation is best effort while an external Docker operation finishes. Closing the worker also requests shutdown and releases its lease. An interrupted observation is never relabelled successful.
For renewal, pause, wait for active work to finish, then Edit / renew. A changed journey/resource scope changes its comparison fingerprint; only grant/cadence renewal preserves it.
History is bounded to 10 targets, 100 configuration revisions per target, 1000 jobs/notices per target plus reserved failure notices, and 10000 append-only reviews per store. Capacity pauses collection. Preview cleanup removes only eligible finished job metadata and read notices older than 30 days. Authorization-to-run links and reviews survive that cleanup.
Evidence retention uses the existing explicit CLI preview/confirmation. Baselines and reviewed runs are protected. No evidence is silently discarded.

## Recovery codes
- RUNNER_OFFLINE: reopen an authorized --monitor session; a regular UI cannot queue work.
- GRANT_EXPIRED: pause/edit and obtain renewed authority. No automatic renewal.
- PILOT_IMAGE_REQUIRED / SOURCE_CHANGED: rebuild for the intended snapshot after confirming the active testing effort.
- PILOT_SCOPE_DENIED / PILOT_REQUEST_FAILED: inspect coverage. Do not broaden origins merely to remove a warning.
- CLEANUP_UNCONFIRMED: stop new work. Inspect exact cem-pilot-JOBID resources. Restart recovery checks labels and removes only resources belonging to that interrupted job. It blocks on ambiguous ownership.
- REMOTE_ENGINE_DENIED / ISOLATION_MISMATCH: restore the supported local engine; never relax sandbox, gateway isolation, caps or mounts.

This guide is an authored procedure. Fresh install, Docker isolation, browser reflow, keyboard behavior and the complete operator task are unverified on this increment.
