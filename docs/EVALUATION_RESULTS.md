# Measured synthetic evaluation

On 2026-09-24, 16 purpose-built scenarios × 3 observation arms × 3 repetitions produced 144 candidate runs, plus 9 baselines. All 153 attempts executed: 132 completed and 21 partial, with no failed, cancelled or unexecuted attempts. A partial observation records a visibility limit; it is not a failed test assertion.

| Pooled candidate metric | HTTP | PAGE | JOURNEY |
|---|---:|---:|---:|
| Candidates | 48 | 48 | 48 |
| Completed / partial | 48 / 0 | 45 / 3 | 30 / 18 |
| Full-scenario script-reference recall | 48/114 | 48/114 | 114/114 |
| Inventory precision | 48/48 | 48/48 | 114/114 |
| Recall within each arm's capability | 48/48 | 48/48 | 114/114 |
| Declared reachable-state coverage | 48/138 | 48/138 | 138/138 |
| Arm-appropriate field completeness | 48/48 | 192/192 | 444/456 |

Inventory identity collapses each fixture resource basename once per run, including references and blocked attempts. It does not prove script download, execution or maliciousness. HTTP field completeness measures the document reference alone; PAGE/JOURNEY add request, response and eligible body hash. The reachable-state denominator excludes intentionally unreachable checkout in T06/T12. Equal arm-specific percentages do not mean equal information or complete checkout coverage.

All 9 baselines completed. JOURNEY change precision and recall were 12/12 on the predefined T02–T05 subset only. Other scenarios and HTTP/PAGE have N/A change scores under the protocol. PAGE does observe the changed catalog body in T04; the metric's applicability does not deny that observation. T08 compares a legitimate dynamic resource against the T01 baseline, not a repeated T08-to-T08 dynamic comparison.

T09/T19 produced 18 incomparable candidate comparisons (6 per arm), retained as unknown rather than clean diffs. PAGE T19 had 3 partial runs. JOURNEY retained 3 partial runs each for T06 selectors, T10 body cap, T11 frame visibility, T12 timeout after an allowed mock-provider redirect, T15 a browser-blocked insecure request and T19 service-worker visibility. The T15 attempt does not demonstrate delivered mixed content. Safety cases T17/T18 belong to separate local suites, outside this benchmark.

Collector-only completed-run medians were HTTP 11 ms (7–65), PAGE 2309 ms (2033–3190) and JOURNEY 4175 ms (3937–4516). Partial JOURNEY observations reached 33689 ms. Container startup is excluded and host load was uncontrolled; these are not general latency, cost or speedup estimates.

Source at execution: `667dfe7ec4ac11287beef0b17603a0a5f876c0543ee52029ea3c61f98078932c`. Seed: 20260924; fixture version: 1; ground-truth SHA-256: `23b42d330ee59e911924da9f2715681cfd0a95e1d6b71348e65a123d46ce5aa0`. See the [protocol](RESEARCH_DESIGN.md), [ground truth](../lab/ground-truth.json), [metric implementation](../benchmarks/metrics.py) and [verification status](TESTING_STATUS.md) for host details and the packaging-only source carry-forward.

All 153 retained sanitized artifacts were integrity-checked and metrics recomputed. An agent reviewed 38 distinct finding templates spanning 1938 findings and identified no unsupported compliance, maliciousness, execution or clean-system conclusion in that bounded review. This is not independent human adjudication. Raw stores, private paths and approval history are excluded from this repository, so the published summary is not independently auditable from raw measured records alone. The shipped fixtures/protocol support a new, explicitly authorized local reproduction.

These purposive synthetic fixtures on one configuration do not estimate general detector accuracy, real-store coverage, compliance or production readiness. No live merchant was scanned.
