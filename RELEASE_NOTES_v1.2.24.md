# Android Cleaner v1.2.24 — Hard Shutdown Lifecycle

Based on the tested v1.2.23 line.

## Fixes
- Closing Android Cleaner now invalidates active scan work, stops the bundled ADB server, closes Tk, and uses a final process-exit barrier so `AndroidCleaner.exe` cannot remain hidden in Task Manager after its window disappears.
- The verified-update handoff uses the same hard shutdown path after launching Setup.
- Inno Setup now terminates stale `AndroidCleaner.exe` and `adb.exe` processes in `PrepareToInstall`, before file replacement begins, then waits briefly for handles to release.

## Preserved
- v1.2.23 unified Problem Started discovery.
- v1.2.22 installer/provenance correction.
- v1.2.21 protected-profile handling.
- No database, shared-knowledge, scoring, removal, or schema changes.
