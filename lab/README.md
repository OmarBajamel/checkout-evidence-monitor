# Synthetic LAB only
The host wrapper creates an unstarted container, inspects its isolation contract, then starts it only with a matching local test session and explicit LAB grant. Public targets are unsupported.
The image is prepared from a pinned Microsoft digest. No image was built or run during implementation. Build prerequisites and commands are in docs/RUNBOOK.md.
Fixture certificates are generated inside the image for .test names only. The CA private key is removed; the synthetic leaf key has no public trust. No host trust store is modified. Ephemeral NSS trust is confined to the container.
The optional SW profile records reduced action/event visibility. No browser sandbox bypass or ignore-HTTPS-errors switch exists.
T01–T24 fixtures and ground truth live under scenarios/. UI/workflow tests T25–T38 are separate from the three-arm benchmark.
