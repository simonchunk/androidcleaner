# Android Cleaner v1.2.29 — Persistent Icon Cache

- Icon cache is now reusable across different customer phones.
- Cache identity uses package + Android versionCode where available, with package + versionName as fallback.
- Install/update timestamps no longer invalidate an otherwise identical app icon.
- Existing local icon files from earlier versions are reused where the identity database can map them.
- Batched native Android rendering remains the cache-miss path; only missing/new app builds need rendering.
- Master Scan, v1.2.28 scan-overlay lifecycle fix, detection rules and connection tools are unchanged.
