# v1.2.8 Local Test — Guaranteed icon trigger

- Moves the icon-pipeline trigger to the table-render completion path.
- Every completed app-table render schedules a UI-thread icon check.
- The worker is guarded against duplicate/recursive launches.
- A candidate signature prevents repeated work after a successful pass.
- Adds `ICON UI TRIGGER` logging before `ICON PIPELINE START`.
- Keeps Android PackageManager/app_process rendering as the primary icon method.
- APK/AAPT2 remains fallback only.
- Icon requests remain limited to CRITICAL/HIGH/CHECK non-protected apps.

Expected first successful log chain:
ICON UI TRIGGER
ICON PIPELINE START
ICON PIPELINE QUEUE
ICON DEVICE ...
