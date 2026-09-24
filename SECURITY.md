# Security and responsible use

This prototype supports OFFLINE review and an isolated synthetic LAB, with bounded local verification documented in [the verification record](docs/TESTING_STATUS.md). It does not support or authorize real-store scanning. Do not enter real credentials, payment details, customer records or secrets. Do not disable sandbox, network-none, TLS, Host/Origin or session checks to obtain a successful run.

Do not file a public issue containing a secret, raw customer evidence or an exploitable target. No monitored security mailbox or response SLA is advertised. If GitHub private vulnerability reporting is explicitly enabled on the published repository, use that channel; otherwise arrange a private contact route with the owner before sharing sensitive details. No private reporting feature is claimed to be enabled by this local package.

Review [the threat model](docs/THREAT_MODEL.md). Container isolation and redaction reduce exposure but are not demonstrated security guarantees. Editable local approval files cannot authenticate intent against a person who controls the filesystem. Hashes detect stored-byte inconsistency, not server authenticity or an adversary who rewrites both data and hashes.
