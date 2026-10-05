# Android Cleaner v1.2.30-rc3 — Release Candidate

- Added live **Popup Hunt** to identify the foreground package while a popup is occurring and promote the observed app to CRITICAL for that scan.
- Strengthened package-name combination detection for generic cleaner/junk/sweep/guard/file/storage-style PUPs without restoring install-time risk.
- Added tiered name resolution: native batch first, targeted suspicious-name resolution before classification, then background AAPT2 completion for unresolved user apps.
- Expanded Android/Samsung battery probing with ASOC and additional cycle/full-capacity nodes; unsupported health now explicitly displays `Health N/A`.
- Icons remain asynchronous and persistently cached so they cannot hold up Master Scan.
