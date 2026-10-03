# Current V1.1 architecture amendment

The original evidence engine below is retained. `pilot/policy.py` validates public guest scopes, `pilot/proxy.py` enforces approved hostname/public-IP egress, `pilot/runner.py` controls inspected isolated containers and `pilot/collector.py` captures bounded observations. No LAB rejection is removed. `operations.py` adds namespaced SQLite tables for configuration history, durable jobs, leases, deduplicated notices, append-only reviews and retained run-to-grant context. The readable schema is `migrations/002_monitoring.sql`.

`cem ui` opens only the workbench; `cem ui --monitor` explicitly starts the single local worker after a PILOT runtime gate. New same-origin authenticated typed API routes create paused targets, request actions, acknowledge notices, append reviews and confirm retention. Four Signal destinations use actual local data; setup, monitoring and inbox are within Assessments. Evidence stays immutable. See [security boundary](PILOT_SECURITY.md), [setup](PILOT_QUICKSTART.md) and [current verification](CURRENT_STATUS.md).

## Historical V1.0 architecture

The runtime is separated from build and publication tooling. Python domain/config/authorization services validate declarative jobs. `lab_wrapper.py` owns Docker creation, inspects the stopped configuration, starts only the recorded immutable local image, monitors budgets and imports the result. `lab/entry.py` starts only synthetic loopback fixtures inside network-none and supervises the collector. Public targets are rejected before lookup.

`collector/cdp.py` keeps one main-page CDP session with bounded Network buffers, completed-length eligibility, a bounded body queue and no fallback refetch. DOM references are metadata only. Unresolved subframe network attribution is explicit and partial; V1 does not promise complete OOPIF/service-worker visibility. The HTTP arm only parses the document and records references. The PAGE arm performs the first declared navigation; JOURNEY follows the bounded actions.

`privacy.py` sanitizes before persistence. `storage.py` uses parameterized SQLite, foreign keys, app-owned files, atomic file replacement and a transaction. An interrupted file-first write becomes an orphan, never an accepted run. `migrations/001_initial.sql` is the static readable copy of the installed migration. Cookie values/raw script bodies have no persisted field. HMAC resource identity uses a local key; the key ID participates in comparison. SHA-256 describes sanitized artifact bytes, separate from captured-body hashes.

`comparison.py` refuses unlike profiles and distinguishes added, changed, not observed in a complete window, ambiguous and unobservable. It also compares observed document headers and cookie attributes where context permits. `rules.py` produces OBS-001–012 with separate applicability, evidence sufficiency and confidence. Missing evidence never provides a clean bill of health. Shared integrity checks block export/comparison when stored bytes disagree.

`api.py` provides seven bounded data routes plus the one-use bootstrap. There is no collection, arbitrary-file or URL-proxy route. CLI and API share Store/rules/report services. The React UI uses actual API services, explicit error states and an isolated labelled demo store. The four screens use original tokens and a locally adapted shadcn Button primitive; system fonts avoid external requests.

Reports are inert HTML, JSON and formula-neutralized CSV. Publication tooling performs a separate explicit file export. Private state, raw records and history are not copied. No app code runs during asset rasterization, schema AST extraction or package build.
