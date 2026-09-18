# v1.2.4 Local Test — Android-rendered icons

- Replaces host-side APK icon parsing as the primary icon method.
- Bundles a tiny DEX/JAR helper compiled during GitHub Actions.
- The helper runs through Android `app_process`, asks PackageManager for the installed app icon, and lets Android render adaptive icons/vector drawables itself.
- Rendered PNG is pulled over ADB and cached locally.
- Only CRITICAL/HIGH/CHECK apps are requested.
- Existing AAPT2/APK extraction remains as fallback.
- Helper is pushed once per connected device session; temporary PNG files are removed after retrieval.
- APP_VERSION is 1.2.4 and continues to drive GitHub artifact/installer versioning.

Expected artifact: AndroidCleaner-v1.2.4-Installer
