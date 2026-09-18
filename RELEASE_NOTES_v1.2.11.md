# v1.2.11 Local Test — Serial accessor / icon pipeline fix

Root cause found from the v1.2.10 trace.

The CustomTkinter UI class exposes `serial()`, but the new icon pipeline and
diagnostic hooks were calling nonexistent `current_serial()`.

Effects:
- v1.2.9 rendered rows first, then its end-of-render icon hook raised before logging.
- v1.2.10 moved the same bad call to the beginning of apply_view(), so the table
  was cleared/never populated, making every tab appear empty.
- The on-device icon renderer itself still had not been reached.

Fix:
- Replaced all UI-side `self.current_serial()` calls with `self.serial()`.
- Restored the working v1.2.9 scan/display path.
- Kept the icon pipeline instrumentation.
- Added `ICON SERIAL ACCESSOR OK` marker.

Broken calls replaced: 4

Expected log chain:
BUILD MARKER Android Cleaner v1.2.11 Serial Icon Fix loaded
ICON TREEVIEW HOOK
ICON UI TRIGGER
ICON SERIAL ACCESSOR OK
ICON PIPELINE START
ICON PIPELINE QUEUE
ICON DEVICE ...
