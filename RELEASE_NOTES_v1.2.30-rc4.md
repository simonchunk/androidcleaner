# Android Cleaner v1.2.30-rc4

Release candidate focused on live popup diagnosis, app-name reliability and battery health.

- Popup Hunt now shows a live progress panel, countdown, current foreground package, observed-app count and Cancel.
- Newly resolved app labels trigger immediate re-triage, so late name evidence can change Cleanup/Review results without another scan.
- Added Android-label encoding cleanup for mojibake such as `Â Open Browser`.
- Retains native batch names with targeted/background AAPT2 fallback for unresolved user apps.
- Replaced Cleaner battery-health logic with the proven Bench Tool v0.34 Android probe, including Samsung ASOC/capacity_max/BatteryService telemetry and full/design capacity calculation.
- Battery health remains N/A when the phone does not expose trustworthy data.
- Icons remain asynchronous and persistently cached.
