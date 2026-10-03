# Deterministic observation contract
Rules are associated with profile rule_version=obs-1. All rules carry version, preconditions, required evidence IDs, condition, applicability, evidence sufficiency, reason codes, separate confidence and interpretation. NO_MATCH means only that an adequately observed narrow condition was absent. Missing evidence yields INCONCLUSIVE or NOT_RUN. No numeric risk score, CVSS invention or standard verdict.

| Rule | Trigger and evidence | Qualification / false-positive boundary |
|---|---|---|
| OBS-001 | Inventory relevant response headers; compare values in like reached state | Absence/change is contextual; missing response is unknown. Preserve enforcement vs report-only |
| OBS-002 | Record CSP header availability, repeated fields and parsed directives per response | Report-only never counts as enforced; malformed/unsupported syntax is recorded, no bypass/security-strength verdict |
| OBS-003 | Compare Secure/HttpOnly/SameSite attributes for explicitly configured sensitive/session cookie role | UNKNOWN role => manual review, not failure; values never stored; legitimate cross-site purpose matters |
| OBS-004 | Record insecure request attempt and separate response/delivery evidence in an HTTPS state | Blocked attempt differs from delivered mixed content; protocol metadata is not a full TLS audit |
| OBS-005 | New observed external script resource in a comparable reached state/window | Not malicious, not necessarily unapproved, no execution assertion |
| OBS-006 | Different SHA-256 for same resource and identical body representation/context | Dynamic code may legitimately vary; missing/oversized/evicted body never receives a hash |
| OBS-007 | Script origin absent from comparable baseline's complete relevant inventory | Origin is scheme/host/port, not company ownership; do not equate same-site with same-origin |
| OBS-008 | Per-frame/state inventory of external script DOM references and requests/responses | References, fetches and executions are separate; third-party means origin relationship only |
| OBS-009 | Bounded DOM metadata contains integrity attribute for observed external script | Presence alone does not prove correct digest/enforcement; absence does not exclude alternate integrity controls |
| OBS-010 | Declared checkout state not reached, blocked step or unexpected redirect | Coverage finding; dependent checks NOT_RUN; never infer disappeared scripts |
| OBS-011 | Event/body/session/time/output cap or collector error occurred | Mark affected scope PARTIAL; retained inventory may still be useful; no universal absence claim |
| OBS-012 | Profile mismatch, key mismatch, ambiguous identity or unlike hash representation | Refuse/qualify comparison with exact reason, never coerce consent/auth/representation equivalence |

OBS-005/007/008 may produce one grouped finding with multiple facets, avoiding duplicate alerts for the same resource. Severity is INFO/REVIEW_NEEDED/ERROR for operational prioritization, not exploitability. Human explanation names journey stage and suggested investigator (store integration owner, frontend team, security reviewer); no invented conversion or revenue loss.

Primary references: Playwright CDP documentation and the versioned source URLs in src/cem/data/asvs-subset.json. The exact supported set is OBS-001 through OBS-012; malware classification, script execution tracing, full CSP analysis and automatic compliance grading are excluded.
