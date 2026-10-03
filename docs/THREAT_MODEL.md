# Current V1.1 threat-model amendment

The original OFFLINE/LAB boundary below remains applicable to that adapter. The new externally connected PILOT uses a separate image and wrapper; its threat model, mandatory controls and residual limits are in [PILOT_SECURITY.md](PILOT_SECURITY.md). The old statement that there is no public adapter is historical. New queue/configuration/review writes use bounded typed JSON, same-origin bearer protection and SQLite transactions. Grants are local operator attestations, not authenticated authority. Runtime enforcement and recovery have not yet been verified for this source.

## Historical V1.0 boundary

Assets: local sanitized evidence, local identity key, API session token, output integrity, host filesystem and approved target scope. Trust boundaries: operator-supplied JSON → strict parser; fixture/browser → capture → sanitization; filesystem → SQLite/artifact verification; web origin → loopback API; private workspace → public export.

| Threat | Implemented control | Residual limitation |
|---|---|---|
| Public/private/metadata/IPv6 destination | No public adapter; exact LAB names/ports/actions; route checks plus network-none container inspected before start | Host/Docker administrator and kernel remain trusted; no claim against container escapes |
| Unsafe transaction or executable journey config | Finite action vocabulary, fixed selectors/values, GET-only resource scope, stop action, no arbitrary JS | Fixed collector instrumentation executes solely to read DOM metadata |
| Browser compromise/excess resource use | Nonroot Chromium sandbox, seccomp, drop-all caps, no-new-privileges, read-only root, PID/CPU/memory limits, bounded capture and output | Host bind output is monitored and writer size-capped, not a general filesystem quota; synthetic trusted fixture boundary is essential |
| DNS rebinding or cross-origin local access | Exact Host, no forwarded headers, exact Origin, fetch-site checks, no CORS, memory-only bearer, one-use bootstrap | A compromised host process/user can read process memory or change local files; not defended |
| Evidence XSS or CSV formulas | React text rendering, no HTML injection, CSP, no remote assets, Jinja autoescape, CSV prefix neutralization | Export consumers must preserve protective quoting and labels |
| Secret leakage | No request/cookie values, limited headers, URL identity digest, query/path redaction, stable errors, inert previews | Redaction is scoped to synthetic data, not a guarantee for arbitrary real-world PII |
| Corrupted or interrupted local state | Artifact+database hash consistency, transactional relationships, explicit orphan status, baseline/export guards | Editable hashes are not signatures or tamper-proof provenance |
| Accidental testing/publication | Source-bound opt-in guards, manual workflow, separate publication plan/export binding | Editable workflow records do not authenticate humans |
| Supply-chain/rights error | Exact binary locks, npm integrity, disabled lifecycle hooks, reviewed static builds and source notices | No vulnerability-free dependency assertion; runtime compatibility unverified |

No exploit testing, remote scanner service, merchant credentials, LLM, paid API, cloud compute or telemetry is required. Detailed limitations and future assertions are in LIMITATIONS.md and the authored test catalog. No runtime security assurance has been measured.
