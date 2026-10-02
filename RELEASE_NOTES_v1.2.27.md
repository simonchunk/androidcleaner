# Android Cleaner v1.2.27 — Batched Native Icons

- Keeps the v1.2.26 Master Scan behaviour unchanged.
- Reworks suspicious-app icon loading into one batched Android `app_process` renderer call.
- The phone rasterizes adaptive/vector icons natively at 96 px and streams PNG bytes back over one `adb exec-out` connection.
- Cached icons are skipped before the batch request.
- Scan results remain usable while icons load; icon loading no longer drives the scan progress overlay.
- Retains the proven v1.2.26 per-app/APK renderer only as a compatibility fallback when the batch renderer returns no icons.
- Historical release-note files are no longer carried in each source package; the project Hub/recovery archive is the history.
