# v1.2.3 Local Test

Build/version hotfix:
- Fixes startup NameError by defining APP_VERSION before APP_NAME.
- GitHub Actions now reads APP_VERSION directly from android_cleaner.py.
- Inno Setup receives that same version from GitHub Actions.
- Installer filename, SHA256 filename and GitHub artifact name all derive from the same APP_VERSION.
- Removed stale hard-coded v1.1.0 values from the Windows build workflow.
- The Inno script now fails the build if a version is not supplied, preventing silent stale-version installers.

Expected GitHub artifact for this source:
AndroidCleaner-v1.2.3-Installer
