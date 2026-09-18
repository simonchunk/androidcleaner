# Android Cleaner v1.1.0

## Diagnostic information upgrade

- Adds Android app icons beside app names when a raster launcher icon can be extracted from the APK.
- Reuses the existing APK pull/name-resolution pass, so no additional app is installed on the customer's phone.
- Caches icons locally by APK SHA-256 to avoid repeatedly pulling the same icon.
- Expands App Assessment with version, install source, first-installed and last-updated information.
- Makes active special access prominent in App Assessment: Accessibility, Device Admin, Notification access, Overlay and Install unknown apps.
- Keeps existing Cleanup/Review decisions and Shared Knowledge behaviour unchanged.
- No knowledge database schema change.
