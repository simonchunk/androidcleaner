# Android Cleaner v0.18.7

Deployment polish release.

- Fixes the post-update relaunch issue that could briefly show a `python312.dll` / `_MEI` error after a successful upgrade.
- The updater now closes the old build and lets the installer complete without auto-launching a second PyInstaller instance. Reopen Android Cleaner from the normal shortcut after the installer finishes.
- Removes Cross-PC Test Mode from the production Admin menu.
- Keeps the verified GitHub/certifi updater and SHA-256 verification introduced in v0.18.5.
- No database or knowledge-schema changes. Existing workstation settings and learned intelligence are preserved.
