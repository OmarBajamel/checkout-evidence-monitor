# Current local increment
Version: V1.1 dual-purpose / package 0.2.0a1. Experimental 0.2.0 alpha release line.

The current source contains Signal integration, a guided paused-target setup, a separate bounded PILOT collector, durable local monitoring, an in-app inbox, append-only review history and review export. It retains the synthetic LAB and its research adapters.

This increment is awaiting runtime testing. The September 24 tests, benchmark and public v0.1.0-prototype release apply to their historical snapshot only. No new merchant observation, participant study, app preview or publication was performed while implementing this increment.

## Product boundaries
- Local single-operator prototype; no hosting/accounts, email/webhooks or background cloud service.
- Pilot journeys support authorized public HTTPS pages, exact origins, required visible selectors and GET/HEAD observations. No sign-in, form input, cart mutation, orders or payments.
- A fresh guest context and unset consent can limit checkout compatibility.
- Monitoring requires the explicitly started local runner and an unexpired grant. Missed time is visible.
- Fonts use official family names with system fallbacks. Figma assets are original exported vectors; runtime pixel/reflow fidelity is not yet reviewed.
- The whole dual-purpose project is not operationally complete until a supported end-to-end operator task and reproducibility checks are actually observed.

## Read next
- [Guided setup and recovery](PILOT_QUICKSTART.md)
- [New collection boundary](PILOT_SECURITY.md)
- [Evaluation protocol](EVALUATION_V1_1.md)
- [Historical verification](TESTING_STATUS.md)
- [Signal design gallery](DESIGN.md)

Read the [alpha release notes](releases/v0.2.0-alpha.1.md) for distribution details. Publication status does not establish runtime verification.
