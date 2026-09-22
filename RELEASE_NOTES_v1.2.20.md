# v1.2.20 Deployment Candidate — None-safe OEM scan

Fixes the real Samsung SM-A566B / Android 16 scan failure: `NoneType` had no `strip`.

- Normalises ADB stdout/stderr at the central runner boundary.
- Makes Android property, APK-path, installer and package parsing None-safe.
- Makes hibernation command output None-safe.
- Scan failures now record the full traceback in resolver.log.
- No triage, shared-knowledge, removal, UI layout or App Assessment behaviour changes.
