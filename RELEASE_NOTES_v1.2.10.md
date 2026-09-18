# v1.2.10 Local Test — Scan/UI execution trace

This is a diagnostic build to stop guessing where the CustomTkinter scan/render chain is breaking.

It logs:
- application build marker
- scan entry
- scan-results-ready point
- every Tk `after()` scheduling point
- entry/exit/error of the scheduled `apply_view` callback
- entry/exit/error of the scheduled icon callback
- entry/exit/error of scan-overlay shutdown
- `apply_view` entry itself
- `set_view` and `retriage` entry
- uncaught scan-worker exceptions

No Shared Knowledge URL/configuration is changed in this build.

Expected useful chain:
TRACE SCAN ENTER
TRACE SCAN RESULTS READY
TRACE SCHEDULE ...
TRACE UI CALLBACK apply_view ENTER
TRACE APPLY_VIEW ENTER
ICON TREEVIEW HOOK
ICON UI TRIGGER
ICON PIPELINE START
...
