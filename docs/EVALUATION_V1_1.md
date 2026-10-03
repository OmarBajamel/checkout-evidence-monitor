# Prespecified evaluation — dual-purpose increment
Protocol version: cem-eval-1.1. Authored 2026-09-30; no new experiment or participant task has run.

## Research questions
RQ1: Under the existing fixed synthetic fixtures, how do HTTP, PAGE and JOURNEY differ in reached-state coverage, observable script inventory and defensible change identification?
RQ2: Does the navigation-only public pilot preserve its declared scope under redirects, mixed DNS answers, expiry, cancellation and restart?
RQ3: Can an operator identify a material difference, interpret an unknown outcome and record an appropriate next action using Signal?

## Controlled replication
Freeze source, compiled UI, dependency locks, browser/image digest, fixture/ground-truth hashes, profile and machine environment before executing. Review lab/ground-truth.json and benchmarks/applicability.csv independently of collector output. Preserve the existing synthetic three-arm benchmark; no public pilot data enters its accuracy denominator.
Run all applicable fixtures in each of HTTP/PAGE/JOURNEY with three repetitions using the existing fixed seed and adapter. Retain attempt IDs, intended arm, timestamps, run ID/status, reached states, eligible comparisons, latency and limitation codes. The existing adapter retains its versioned randomization and applicability logic.
Compute each coverage/script/change measure with its own explicitly defined denominator. Report attempted, completed, partial, failed and ineligible counts, not only successful subsets. Missing/incomparable bodies remain unknown; they are not true negatives. Report counts and per-fixture/repetition distributions rather than a universal detector-accuracy headline.
Another evaluator should recompute metrics from retained sanitized artifacts and independently compare manifest hashes. Record environment differences and reproduction failures.

## Additional pilot-control cases
P01: unlisted redirect and POST are denied before dispatch.
P02: mixed public/private DNS responses, IPv4-mapped and transition IPv6 are refused; the dialed address is the validated literal.
P03: unauthenticated/unlisted CONNECT cannot reach DNS or sockets; connection/count/byte/deadline caps close bounded work.
P04: browser bridge has no external route or host-addressed gateway; direct internet, host gateway, metadata, DNS bypass, WebSocket and popup attempts fail in the supported staging harness.
P05: duplicate start/manual triggers do not overlap a target; missed intervals produce one fresh job and an explicit gap.
P06: kill/restart preserves interruption; failed container cleanup blocks a new lease until owned resources are recovered.
P07: grant expiry and pause cancel work, and renewal of scope changes comparability when appropriate.
P08: paths/query values/nonces/cookie values and identity keys never appear in retained artifacts or logs.
P09: immutable artifact bytes survive review decisions; stale retention previews are refused; grant context survives job metadata cleanup.
P10: same-source OFFLINE/LAB permission cannot start PILOT.
Authored offline tests use mocks only. Network-bound staging cases must run under a separately approved pilot test scope; do not substitute an unrelated merchant or disable public-IP checks to make local fixtures work.

## Operator task study
Recruitment and contact are future actions requiring owner direction; no participants are claimed here. Proposed formative sample: 5–8 consenting operators with mixed technical familiarity, using authored synthetic records first. Assign pseudonymous participant IDs and retain only necessary timing/task notes.
Counterbalance the two comparison cases; keep instructions and facilitator prompts fixed. Tasks:
1. Set up a paused target from a written authorized scope, without starting collection.
2. Find the correct baseline/candidate pair and explain why an incompatible pair cannot be compared.
3. Identify a changed script, open both evidence records and explain the difference between request, response and execution.
4. Interpret a partial/unknown case without concluding disappearance or safety.
5. Record a justified next action and export the review bundle.
6. Explain what a missed cadence and expired grant mean, then locate pause/renew controls.
Prespecify success per task: correct result plus correct interpretation without facilitator completion. Capture elapsed time, assistance count, critical interpretation errors, success/partial/failure, and a 1–7 single ease question. Keep unsuccessful and abandoned tasks in the denominator. Do not infer population effects from this small formative sample. Follow-up questions distinguish UI confusion from domain knowledge.

## Operational usefulness
After staging controls pass, select one specifically authorized supported store and a time-bounded public guest journey. Document compatibility, missed resources, operator interpretation and useful/irrelevant notices. A real store lacks complete ground truth; do not report false-positive rates or malware accuracy from it. Avoid customer/account/payment data.

## Outputs
A source-bound experiment manifest; attempt-level CSV; reproducibility instructions; artifact-hash audit; pilot-control outcomes including failures; anonymized task results; threats-to-validity discussion.
Legacy September 24 numbers (153 attempts, 132 completed, 21 partial) remain historical synthetic evidence. They are not results of this protocol or the new pilot.
