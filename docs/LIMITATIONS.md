# Current V1.1 limits — runtime verification pending

This source increment (0.2.0a0) adds a navigation-only public PILOT adapter, Signal UI, durable local monitoring and review history. Its new security controls, UI behavior, fresh installation and complete operator workflow have not been run. The earlier results below apply only to the September 24 source. See [current status](CURRENT_STATUS.md) and [pilot boundary](PILOT_SECURITY.md).

The new pilot supports only explicitly authorized public HTTPS pages, required visible selectors and GET/HEAD observations in a fresh guest context. It cannot complete sign-in, cart mutation, orders or payment. Its output is kernel-bounded tmpfs, unlike the historical LAB output bind described below. Browser/daemon/kernel trust, limited frame visibility, remote GET side effects, missing ground truth and unknown evidence remain material limits. No users have participated in the new task study, and no real store has been assessed.

## Historical V1.0 limits and results

Overall testing is TESTED_PASS_LOCAL for 73 listed pytest cases and the documented installed-package checks. The isolated LAB collector and 153-attempt synthetic benchmark executed, retaining21 partial observations. See TESTING_STATUS.md for the exact evidence. Public concept images remain concepts; authorized fixture screenshots are retained in the private local report.

V1 supports only OFFLINE records and isolated synthetic LAB. No real merchant, payment provider or PrimeOrder assessment is authorized. Windows is the OFFLINE target; Linux x64 Docker is the LAB target. The recorded Linux x64 Docker/WSL2 configuration completed the LAB runs after a bounded chroot seccomp adaptation; normal container cleanup was checked. This is not exhaustive cancellation-path testing, a containment proof or certification of other hosts. Windows OFFLINE installation and UI startup are checked separately. Never bypass safeguards for compatibility.

Journeys use configured fixed actions and short observation windows. Complex commerce platforms, CAPTCHA, authenticated accounts, cross-site real payments, persistent sessions and production egress are excluded. No transaction is submitted. The presence of configured steps is not universal coverage.

Only eligible completed external-script bodies receive hashes. CDP text and base64-decoded representations are distinct. Oversized/evicted/unknown-size bodies retain reasons. Inline scripts have metadata only. Script execution, taint flow, dynamic code attribution and maliciousness are not measured. Service workers and unresolved subframes make coverage partial. Browser route interception alone is not represented as the network boundary.

CSP data is a bounded token inventory, preserving report-only distinctions and unsupported/duplicate directive notes; it is not full grammar validation or a policy bypass test. Repeated header representation depends on what the browser/HTTP library exposes. Cookie attributes apply only to a configured synthetic session role; values are excluded. Mixed-resource attempts and delivered responses differ. TLS metadata is not a full transport audit.

Standards mappings cover eight verified ASVS 5.0.0 identifiers as partial evidence. PCI 4.0.1 6.4.3/11.6.1 are manual context only. ISO/IEC 27001:2022 is discussed at a process level, with no control-number or certification claim. No ASV service, compliance score, clean verdict, vulnerability absence or guaranteed novelty is offered.

Stored artifact hashes detect local inconsistency, not source-server authenticity. Imports are DECLARED_IMPORT even if the input claimed collection. Local approvals and identity-key files are editable. Sanitization is not safe permission to import customer datasets. Output writer limits and host monitoring are not a disk quota against arbitrary hostile container code; V1 stays within isolated shipped fixtures.

The evaluation is a small purposive fixture study with capability-specific denominators and failed attempts retained. The report provides measured raw counts for this synthetic set, not general accuracy: script-reference recall114/114 for JOURNEY versus48/114 for each one-page arm. References and blocked requests are not successful execution. There are no population effect estimates; timing excludes container startup and had uncontrolled host load.
