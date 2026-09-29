# Android Cleaner v1.2.22 — Provenance Hardening

Based directly on the working v1.2.21 protected-profile build.

## Fix
- Retains the foreground-user package scan that prevents Samsung protected profiles / Secure Folder from aborting the scan.
- Stops treating a blank, `null`, or unreported installer as proof that an app was sideloaded.
- `SIDELOADED` now requires explicit Package Installer provenance (`com.google.android.packageinstaller`, `com.android.packageinstaller`, or Samsung Package Installer).
- Missing installer provenance is displayed as `Unknown / not reported` and does not receive the sideload risk boost.
- This also prevents ordinary apps with missing provenance from unnecessarily entering suspicious icon-resolution work.

## Unchanged
- No database schema changes.
- No shared-knowledge changes.
- No changes to known-safe/known-malware reputation handling.
- No changes to removal, repair outcomes, system/OEM protection, or the v1.2.21 protected-profile fix.

## Test target
Re-scan the Samsung that showed ~112 apps as sideloaded. Confirm normal apps with missing installer data are no longer labelled SIDELOADED, while a genuinely manually installed APK still is when Android reports Package Installer as its source.
