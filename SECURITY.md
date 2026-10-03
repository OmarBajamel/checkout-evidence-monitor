# Security policy and responsible use

[English documentation](docs/README.md) · [التوثيق العربي](README.ar.md) · [Deutsche Dokumentation](README.de.md)

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/OmarBajamel/checkout-evidence-monitor/security/advisories/new) for security-sensitive findings. Do not include customer records, live access tokens, bootstrap URLs or unnecessary exploitable-target details. A minimal synthetic reproduction and affected version are preferable.

No monitored email address, response-time commitment or support SLA is advertised. If the private-report form is unavailable, open a non-sensitive issue asking for a private reporting route; withhold vulnerability details until a channel is agreed.

للبلاغات الأمنية الحساسة استخدم الرابط الخاص أعلاه. لا تنشر بيانات العملاء أو رموز الوصول أو تفاصيل استغلال في بلاغ عام. يمكن كتابة البلاغ بالعربية أو الإنجليزية.

## Version status

| Version | Security/verification posture |
|---|---|
| 0.2.0 alpha | Experimental; static/build review only; runtime and new PILOT controls pending validation |
| v0.1.0-prototype | Historical bounded local verification; no ongoing security-maintenance guarantee |

Neither version is certified, production-hardened or a substitute for a security assessment.

## Authorized use and boundaries

OFFLINE reviews records. LAB runs only shipped synthetic fixtures in network-none isolation. Experimental PILOT supports a separately authorized, bounded public guest journey using an isolated browser and allowlisted proxy; it does not authorize arbitrary scanning.

Do not enter real credentials, payment details or customer datasets. Never disable sandbox, TLS, Host/Origin, session, gateway or scope checks for compatibility. GET/HEAD restrictions cannot guarantee that a remote endpoint has no side effects; exact scope review remains necessary.

Read the [threat model](docs/THREAT_MODEL.md), [pilot controls](docs/PILOT_SECURITY.md) and [limitations](docs/LIMITATIONS.md). Local approval records are editable workflow aids, not identity proof. Artifact hashes detect stored-byte inconsistency, not server authenticity or an attacker who can rewrite both data and hashes.

The public repository excludes private grants, records, browser profiles and raw capture histories. Publication does not start collection, deploy a service or dispatch CI.
