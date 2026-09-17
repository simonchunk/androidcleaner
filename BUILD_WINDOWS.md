# Android Cleaner v0.18.7 - Windows installer build

This build produces a real Windows Setup EXE using GitHub Actions + Inno Setup.

The installer places Android Cleaner under Program Files, registers it in Windows Installed apps, creates Start Menu and optional Desktop shortcuts, and bundles ADB/AAPT2. No Python, SETUP.bat, Android SDK, or loose portable folder is required on the staff PC.

Persistent workshop data remains under `%LOCALAPPDATA%\TheiPhoneGuyAndroidCleaner`, so installing/updating/uninstalling the program does not overwrite the learned database or workstation configuration.

GitHub workflow artifact:
- `The-iPhone-Guy-Android-Cleaner-Setup-v0.18.7.exe`
- matching `.sha256`
