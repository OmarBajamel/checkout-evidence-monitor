# Upgrading from v0.1.0

[Documentation](README.md)

0.2.0 is an alpha with unverified runtime migration and recovery behavior. Keep the earlier release available and evaluate the alpha on a separate copy of your local data.

1. Stop any CEM process or collector you started. Do not copy an actively written SQLite store.
2. Back up the complete private evidence directory, including artifacts, SQLite sidecar files if present and its identity key. Keep this backup private; a Git clone is not a data backup.
3. Check out the new tag in a separate directory and follow [source preparation](GETTING_STARTED.md).
4. Review the new [pilot boundary](PILOT_SECURITY.md). Existing LAB permission does not authorize public PILOT collection.
5. A previous source-bound runtime session or image cannot authorize changed source. Create a new session only within your deliberate local verification effort.
6. Validate a copied store before relying on it. The alpha adds namespaced monitoring tables when opening a writable workbench; existing observations remain separate from review annotations.
7. Keep new targets paused until their actual authority and profile are reviewed. Starting `cem ui --monitor` explicitly starts the worker and can resume previously enabled unexpired cadences.

The original evidence fields remain compatible by design, but migration compatibility is not yet proven by current runtime tests. Do not downgrade a modified live store in place. To return to v0.1.0, use the earlier source with the untouched pre-upgrade backup.

No command here deletes data. Retention remains an explicit preview/confirmation operation; baselines and review-linked evidence are protected by the authored policy.
