# Android Cleaner Changelog

## 1.2.30-rc1 — 2026-10-02
- Restored fast Master Scan behaviour: icon and app-label enrichment cannot hold scan completion.
- Persistent icon cache now keys by package name for maximum reuse across customer phones.
- Removed automatic slow per-app/APK icon fallback from the post-scan icon pipeline.
- Added native Android batch app-label discovery through the existing app_process helper. This improves OEM/OPPO app visibility, including unusual labels such as `#Contacts` and `#Messages`, without pulling complete APKs.
- Added asynchronous Android battery diagnostics: charge level, temperature, voltage, charging state, cycle count and calculated health where trustworthy full/design capacity data is exposed.
- Added one-time What's New window for each installed release candidate, plus Advanced > What's New.
- Master Scan remains timing-independent: install/update dates do not create risk findings.

## 1.2.29
- Added persistent icon caching across phones using app build identity.

## 1.2.28
- Decoupled scan overlay completion from background icon/name enrichment.

## 1.2.27
- Added batched native Android icon rendering.

## 1.2.26
- Replaced Problem Started/time-window workflow with one Master Scan. Install timing no longer contributes risk.

## 1.2.25
- Added staff connection tools including Restart ADB, driver help and Device Manager access.
