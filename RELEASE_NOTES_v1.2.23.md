# Android Cleaner v1.2.23 — Unified Onset Discovery + Clean ADB Shutdown

Based directly on confirmed-working v1.2.22.

## Changes
- When **Problem started = Unknown**, Android Cleaner now evaluates all supported onset windows and surfaces the strongest useful result. Staff no longer need to cycle Today / Last 3 days / About a week / Few weeks / About a month just to discover candidate apps.
- Selecting a specific Problem Started value still applies that actual timing window, so timing remains useful for correlation.
- Broad Unknown results that were promoted by a possible timing window are annotated with the matching window.
- Normal application close now sends `adb kill-server` before exiting.
- The built-in updater also stops ADB before launching the verified installer.
- Inno Setup defensively terminates a leftover `adb.exe` at install time, covering upgrades from older/crashed versions.

## Unchanged
- v1.2.21 protected-profile / Samsung Secure Folder handling.
- v1.2.22 installer-provenance hardening.
- Risk rules, reputation/shared-knowledge policy, DB schema and removal workflow.
