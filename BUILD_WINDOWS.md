# Android Cleaner v1.1.0 - Production Windows installer build

Run the GitHub Actions workflow **Build Windows Android Cleaner Installer**.

The workflow builds the self-contained Windows application, stages ADB and AAPT2, compiles the Inno Setup installer, creates a SHA-256 sidecar, and uploads both as the workflow artifact.

Expected release assets:
- `The-iPhone-Guy-Android-Cleaner-Setup-v1.1.0.exe`
- `The-iPhone-Guy-Android-Cleaner-Setup-v1.1.0.exe.sha256`

Publish them under GitHub release tag `v1.1.0` on the Production channel. Existing `%LOCALAPPDATA%\\TheiPhoneGuyAndroidCleaner` data is not replaced by the installer.
