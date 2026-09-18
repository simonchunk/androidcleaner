# v1.2.5 Local Test — Root IconFetcher build fix

- APP_VERSION bumped to 1.2.5.
- `IconFetcher.java` now lives at the repository root.
- GitHub Actions now compiles root-level `IconFetcher.java`.
- Added an explicit workflow check with a clear error if `IconFetcher.java` is missing.
- The compiled `icon-helper.jar` is still bundled automatically into the Windows installer.
- Android-rendered PackageManager icon pipeline from v1.2.4 is unchanged.

Expected GitHub artifact:
`AndroidCleaner-v1.2.5-Installer`

Expected installer:
`The-iPhone-Guy-Android-Cleaner-Setup-v1.2.5.exe`
