# Local verification status

Current local V1.1 / 0.2.0a0 source is **IMPLEMENTED_NOT_TESTED**. The results below are historical and do not validate the new increment. Read [current status](CURRENT_STATUS.md) and [the pilot quickstart](PILOT_QUICKSTART.md).

Historical v0.1.0 outcome: **TESTED_PASS_LOCAL** as of 2026-09-24, for the bounded OFFLINE_AND_LAB profile and listed assertions. The synthetic LAB collector and three-arm benchmark executed. This is not exhaustive acceptance, production readiness, real-store compatibility or standards compliance.

Source snapshot: `90ebe7dce0175b1c75eb5e3b8441c3add5d0f0bb7c1432fb7d931b1fbc842d96`.

| Category | Actual result |
|---|---|
| Unit and metric-denominator tests |19 passed|
| Security boundary tests with local values/mocks |14 passed|
| Storage/API integration tests |6 passed|
| Local publication/content guard tests |8 passed|
| Chromium UI tests |6 passed|
| Isolated Docker LAB cases T01–T20 |20 passed|
| Combined unique pytest cases |73 passed; 0 failed; 0 errors; 0 skipped|
| Storybook |16 prior cases retained for byte-identical frontend; 8 stories at 1440/390 widths|
| Fresh installed-wheel smoke |20 steps passed using isolated installed imports|
| Three-arm benchmark |153/153 attempts executed: 132 completed, 21 partial; 9 baselines+144 candidates|

The 53 OFFLINE/UI cases and 20 installed-wheel steps ran on `667dfe7ec4ac11287beef0b17603a0a5f876c0543ee52029ea3c61f98078932c`. The 20 LAB cases ran on `8c73919694215658725ac755322a17997bc9b354fbcf563caf3d564828ef6993`; only a nonexecuting image-lock status label, the public content-status assertion and its test index changed afterward. Collector, fixtures, sandbox, limits and dependencies are byte-identical. The final benchmark ran 153 containers built from that same runtime-tested source. The only later source change adds private-root exclusions to the source-archive build; all executable code, dependencies, tests, fixtures and sandbox bytes are identical. Runtime results carry forward for unchanged behavior, and the rebuilt package is audited separately. Storybook was not rerun because frontend source, config, lock and compiled assets match its prior tested bytes.

Twenty-four actual synthetic imported-record UI captures were reviewed at 1440, 1024 and 390 widths:18 refreshed images were inspected directly, 6 matched prior inspected hashes. Keyboard focus/return, accessible names, dialog geometry, reduced motion and overflow checks passed. No screen-reader session, exhaustive computed contrast, browser-zoom audit or full WCAG conformance is claimed. The Starlette test-client emits a nonblocking httpx deprecation warning.

The local study used 16 purpose-built scenarios × 3 arms × 3 repetitions, retaining all partial evidence. Pooled full-scenario script-reference recall was HTTP48/114, PAGE48/114, JOURNEY114/114; this includes references/blocked attempts, not proof of execution. JOURNEY eligible change precision/recall were12/12 on T02–T05 only. Perfect counts on this small fixture set are not general detector accuracy. Timing excludes container startup and experienced uncontrolled host load. See [measured results and limitations](EVALUATION_RESULTS.md). Original attempt records and agent conclusion review remain private; the public package contains the authored fixtures and reproducible protocol, not the raw measured records.

Host: Windows 10 Pro 19045; Python 3.12.14; Node 24.19.0; Playwright 1.63.0/Chromium 153.0.8010.12; Docker Desktop 4.92.0.240144, engine 29.8.0, Linux x64/WSL2. An explicitly reviewed local seccomp adaptation permits chroot for Chromium sandbox initialization. Containers retain nonroot, network-none, cap-drop ALL, no added capabilities, no-new-privileges, read-only root and resource limits. The successful runs do not separately verify every abort/cancellation path or other hosts.

Earlier disk, Docker/WSL and browser-sandbox failures remain preserved. The public source package and status artwork were refreshed after this verification. No remote CI, deployment, LinkedIn posting or real-merchant scan is part of these results. Private approval records, raw stores and local paths are excluded from public export.

Final packaging review caught a duplicate historical README under reports/ in the source archive; nothing was published. Explicit private-root exclusions now prevent that inclusion. The original candidate and failed review are preserved. This packaging-only change and its source hashes are documented in the private packaging review record.

Publication preparation changed documentation and inert artwork only. The 8 local publication/content checks describe the prepublication state; private editorial readiness later transitions to published-link drafts and is not a new runtime-test claim.
