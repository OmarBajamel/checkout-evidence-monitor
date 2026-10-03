# ADR 002 — independent, bounded public pilot

Status: implemented in 0.2.0 alpha; runtime enforcement unverified.

The original network-none LAB remains a synthetic research adapter. Public storefront observation uses a separate image, policy, collector and wrapper. Removing the LAB rejection would erase its trust boundary, so the two adapters remain distinct.

PILOT supports exact ASCII HTTPS origins, port 443, explicit read-only navigation paths, required visible selectors, fresh public guest sessions and grants of at most eight hours. Forms, account actions, cart mutations, orders and payments are excluded.

The browser joins an internal IPv4 bridge in isolated gateway mode. A separate authenticated CONNECT proxy resolves every allowed hostname, rejects any non-public DNS answer and dials a validated literal address. Playwright constrains methods and paths inside the TLS tunnel. The proxy does not inspect encrypted HTTP paths; host/daemon/kernel and authorized remote-origin behavior remain trust assumptions.

A narrow read-only input bind, bounded tmpfs output, sandbox, dropped capabilities, resource budgets and inspected container configuration are mandatory. An unavailable control stops execution; cleanup ambiguity blocks new work.

The UI adds typed same-origin authenticated writes for paused target configuration, explicit worker actions, inbox acknowledgement and append-only review decisions. No scan starts on opening the ordinary workbench. Evidence remains separate from operator interpretation.

Consequences: substantial checkout flows are unsupported, collection requires the local runner and actual scope authority, and static inspection cannot establish containment. Validate the staged controls in [the protocol](../EVALUATION_V1_1.md) before operational use. See [the complete boundary](../PILOT_SECURITY.md).
