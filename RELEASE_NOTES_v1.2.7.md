# Android Cleaner v1.2.7 — local test

- Fixes the icon pipeline not starting after a normal completed scan when no name-resolution/retriage pass was required.
- Starts suspicious/review icon discovery explicitly after scan results are committed.
- Adds deterministic resolver logging for the full icon path: pipeline start, queued package, helper discovery/push, `app_process`, remote PNG size, pull, cache/UI result, and pipeline finish/cancel.
- Keeps icon work limited to CRITICAL/HIGH/CHECK non-protected apps.
- Retains Android framework rendering as primary and APK parsing only as fallback.

Local test build only; do not publish as a GitHub Release.
