# Android Cleaner v1.1.0

## Diagnostic information upgrade

- Adds Android app icons beside app names when a raster launcher icon can be extracted from the APK.
- Reuses the existing APK pull/name-resolution pass, so no additional app is installed on the customer's phone.
- Caches icons locally by APK SHA-256 to avoid repeatedly pulling the same icon.
- Expands App Assessment with version, install source, first-installed and last-updated information.
- Makes active special access prominent in App Assessment: Accessibility, Device Admin, Notification access, Overlay and Install unknown apps.
- Keeps existing Cleanup/Review decisions and Shared Knowledge behaviour unchanged.
- No knowledge database schema change.

## Local UI test adjustment
- Main app-list rows increased from 25 px to 40 px.
- App icons increased to 30 × 30 px.
- Icon gutter widened from 42 px to 46 px.
- App-name column widened where necessary.
- Local test only — do not publish as a GitHub Release yet.

## Local adaptive-icon test
- Adds adaptive launcher icon discovery from common mipmap/drawable XML resources.
- Uses bundled AAPT2 xmltree output when the APK contains compiled binary XML.
- Composites raster adaptive foreground/background layers into a cached PNG.
- Retains raster-icon fallback and the 40 px row / 30 px icon layout.
- Unsupported vector-only layers fail safely with a blank icon and resolver-log entry.
- Local test only; do not publish this build as a GitHub Release yet.

## Local UI/diagnostics iteration
- Adds a separate progressive background icon pass for the full app inventory, rather than only apps selected for label resolution.
- User apps are prioritised before protected system/OEM apps; icons remain cached by APK hash.
- SYSTEM / OEM and UPDATED SYSTEM apps are visually subdued and explicitly protected from removal.
- App Assessment identifies protected system apps.
- Adds Appearance modes: Light, Dark and Follow Windows, persisted per workstation.
- Dark mode uses dark risk colours while retaining CRITICAL/HIGH/CHECK distinction.
- Local test only — do not publish this build as a GitHub Release yet.

## Fix 1
- Fixes startup crash caused by an incorrect `load_config()` helper reference.
- Appearance now uses the application's existing `load_settings()` / `save_settings()` system.
