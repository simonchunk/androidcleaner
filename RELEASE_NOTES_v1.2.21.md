# Android Cleaner v1.2.21

## Protected-profile / multi-user scan fix

- Fixes a scan failure seen on a Samsung device where Android Package Manager returned `SecurityException: Shell does not have permission to access user 150`.
- Package inventory is now explicitly scoped to the device's foreground Android user (`am get-current-user`).
- System, third-party and disabled-package inventories use the same user scope.
- Protected Samsung Secure Folder, work-profile or secondary-user package spaces are not bypassed or accessed; they are simply outside the scan scope when ADB shell does not have permission.
- Falls back conservatively to Android user 0 if the foreground user cannot be resolved.
- No changes to risk scoring, shared knowledge, removal workflow, database schema or UI layout.

Baseline: v1.2.20 stable/deployed.
