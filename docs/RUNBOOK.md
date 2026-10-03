# Operator and build runbook

For the local V1.1 / 0.2.0a0 increment, begin with [PILOT_QUICKSTART.md](PILOT_QUICKSTART.md). New implementation is awaiting runtime verification. The tested status and LAB-only procedures below describe the earlier snapshot unless explicitly reused in that quickstart.

## Environment and historical verification

Historical v0.1.0 runtime verification was TESTED_PASS_LOCAL for the listed assertions; the current alpha is unverified. see TESTING_STATUS.md for exact source provenance, carry-forward checks and limits. Selected runtimes: Python 3.12.14; Node 24.19.0; Playwright 1.63.0 / Chromium 153.0.8010.12 revision 1243. Windows OFFLINE and Linux x64 Docker LAB are intended targets. Do not infer other-platform compatibility. No global install is required.

Use README static preparation on Windows. On Linux, create `.venv` with Python 3.12 and substitute `.venv/bin/python` and `requirements-dev-linux.lock`. Install binary wheels with `--only-binary=:all: --require-hashes --no-compile`; install the built CEM wheel with `--no-deps`. The Windows and Linux transitive locks intentionally differ in greenlet because wheel availability differs; each is exact and hashed. npm lifecycle scripts are disabled in `.npmrc` and command arguments. Do not run esbuild's postinstall fallback downloader manually.

`npm run build` in frontend performs only the source bundle. The wheel includes `src/cem/web`. `python -m build --no-isolation` uses the reviewed static Hatchling configuration, with no CEM import or test hook. Do not start Vite, Storybook, the CLI, fixture servers or containers during implementation-only work.

## Explicit local runtime authorization

After a direct TEST APPROVED for this source and local profile, the private operator records the actual wording/time/source snapshot in their workflow. In the original workspace, `state/APPROVAL_RECORD.json` must reflect that real grant. It is absent from a clean public export, where the local operator's explicit command records their own intent.

```powershell
.venv/Scripts/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE_AND_LAB
$env:CEM_TEST_SESSION=(Resolve-Path .cem-private/test-session.json).Path
.venv/Scripts/cem --help
```

The session expires after four hours and binds the source snapshot. On Linux, use `.venv/bin/python`, `.venv/bin/cem`, and `export CEM_TEST_SESSION="$PWD/.cem-private/test-session.json"`. A source change makes the old session stale; renew only within the authorized testing effort. The record is editable workflow metadata, not authenticated identity proof. Keep it out of public history.

## OFFLINE review

`cem import path/to/sanitized-run.json` accepts a bounded CEM Run JSON contract. Imported provenance is always DECLARED_IMPORT. Use a new app-owned `.cem-data` directory; `CEM_DATA_DIR` may select a directory within the current project. The UI never imports arbitrary files through a URL.

```text
cem list
cem show <run-id>
cem compare <baseline-id> <candidate-id>
cem baseline <run-id> --reason "Reviewed synthetic comparison window"
cem integrity <run-id>
cem report <run-id> --format html --destination reports/local-review.html
cem recovery
cem retention <run-id>
cem retention <run-id> --confirmation <token-returned-by-preview>
cem ui
```

The `retention` token binds the exact selected IDs, not a filesystem path. Selected baselines are protected until replaced. Retention is explicit and deletes only known app-owned files; interrupted writes remain visible in `recovery`. Do not delete arbitrary recovery artifacts without a separate review. `report` preserves existing destinations.

`cem ui` binds `127.0.0.1:8760` and prints a bootstrap URL. Open it locally within 60 seconds; its fragment is cleared before API use. Do not share it. Each bootstrap is single-use, a new bearer is held only in memory, and access expires after 30 idle minutes or eight hours. Reloading loses that bearer; restart the local CLI for a fresh session. Ctrl+C shuts down the owned local server. No automatic browser launch occurs. `--demo` uses a separate `.cem-demo` store with authored examples, visible labels and read-only baseline behavior.

## Isolated Linux LAB

Use a non-root Linux user with an explicitly authorized Docker engine. V1 requires a non-root Chromium sandbox, compatible seccomp/namespaces, no capabilities, read-only container root, bounded memory/CPU/PIDs, private IPC, ephemeral /tmp, no published ports, and `--network none`. The pinned seccomp file includes one reviewed local chroot allowance for Chromium user-namespace sandbox initialization, with no container capabilities added. A host with unavailable Docker or sandbox support must stop with ISOLATION_UNAVAILABLE; never substitute a host browser or `--no-sandbox`.

After local testing authorization, run `PYTHONPATH=src .venv/bin/python tools/build_lab.py`. This creates a fresh `.cem-private/lab-build` context, downloads hash-locked Linux wheels and the pinned Ubuntu NSS certutil package, builds from the pinned Playwright base, and records the resulting immutable local image ID with the source snapshot. The base image is fetched by Docker if not available. It does not start the image. An existing build directory is preserved; review it before choosing a new clean testing workspace.

Copy `examples/synthetic-lab-job.json` to `.cem-private/job.json`. The shipped grant is intentionally expired. Set the exact operator/assessor, fresh timezone-aware issue/expiry timestamps (at most eight hours), fixture T01–T24, exact `.test` origins and listed actions. Keep synthetic inputs only; stop before a transaction. Then run `cem collect .cem-private/job.json --profile LAB` with the matching LAB session. Each stopped container is inspected before start. Fixture TLS trusts a synthetic CA only in its disposable home; `ignore_https_errors` remains false. The wrapper retains bounded partial/failure evidence and removes only its own container/input secrets.

## Optional verification

After approval, run `.venv/.../python -m pytest tests/unit tests/security tests/integration tests/publication` for offline cases. Run `tests/browser` only with the recorded LAB image; run `tests/ui` only with explicitly authorized local browser installation and the compiled UI. The UI suite starts a loopback test server and permits only its local requests. No real target is used. Storybook has a separate guarded `npm run storybook` entry; never start or build it during implementation-only work.

Run `PYTHONPATH=src .venv/bin/python -m benchmarks.run` only under the LAB grant after correctness cases. Retain failures and actual denominators. Inspect actual screenshots and write `reports/VISUAL_REVIEW.md`; a test exit code is not visual inspection. Bind reports to the actual source snapshot and update stale verification after fixes. Do not dispatch the optional remote workflow as part of local testing or publication.

## Failures and privacy

AUTH_REQUIRED: restart the local UI session. INCOMPATIBLE_PROFILE: inspect exact differing context rather than force a comparison. INTEGRITY_FAILED: inspect stored file and database consistency. BODY_UNAVAILABLE/OVERSIZED: preserve the observation with no invented hash. ISOLATION_UNAVAILABLE: repair the compatible local environment, never relax its safeguards. Runtime errors expose stable codes rather than collected exception text. Redaction is conservative for this synthetic scope; it is not a general PII anonymizer for real customer data.
