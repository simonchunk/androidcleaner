# v1.2.2 Local Test

- Window title now derives from APP_VERSION, so test builds visibly show the correct version.
- Light mode contrast strengthened across table/header/risk rows.
- Scan overlay now shows real metadata progress (count + percentage), then closes when the primary scan completes.
- Scan overlay is also closed on errors, stale scans and no-device exits.
- Protected types fixed for actual values: SYSTEM, OEM / SYSTEM, SYSTEM / OEM, UPDATED SYSTEM.
- Protected rows show a lock instead of a checkbox and are filtered out of all removal actions.
- Icon discovery now understands split APK installs and searches density splits before base.apk.
- Icon work remains restricted to CRITICAL/HIGH/CHECK apps.
