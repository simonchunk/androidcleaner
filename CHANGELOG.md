# Android Cleaner Changelog

## v1.2.30-rc4
- Added live Popup Hunt progress/diagnostic panel with countdown and Cancel.
- Resolved app names now trigger immediate re-triage.
- Added Android-label encoding cleanup.
- Ported the proven Bench Tool v0.34 Android battery-health probe, including Samsung ASOC/capacity_max telemetry.
- Kept Health N/A when no trustworthy health value is exposed.

## v1.2.30-rc3
- Added live Popup Hunt foreground-owner capture.
- Strengthened multi-token package-name risk evidence.
- Added tiered native + targeted AAPT2 + background app-name resolution.
- Expanded Samsung/OEM battery health and cycle probes, with explicit Health N/A fallback.
- Kept icons fully asynchronous and cached.

## 1.2.30-rc2
- Restored strong workshop risk classification without restoring install/onset timing risk.
- Cleaner/junk/sweep/booster/storage combinations now promote from their own independent evidence.
- Human-readable Android labels are batch-resolved before final risk classification and All Apps display.
- Native label helper now checks suspicious launcher/activity alias labels, targeting ColorOS/OPPO `#` apps.
- Icons remain post-scan and persistently cached by package name.
- Expanded device header so battery diagnostics are no longer clipped.
- Battery diagnostics remain best-effort and do not invent unsupported health values.
- Added/updated one-time What's New summary for this release candidate.

## 1.2.30-rc1
- Added Android battery diagnostics, What's New and rolling changelog.
- Added native background Android label pass.
- Decoupled icon work from Master Scan.

## 1.2.29
- Added persistent package icon cache.

## 1.2.26
- Introduced Master Scan and removed problem-onset timing from risk scoring.
