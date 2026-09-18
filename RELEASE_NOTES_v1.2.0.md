# Android Cleaner v1.2.0 — Local Test

## CustomTkinter UI rebuild
- Main application chrome rebuilt in CustomTkinter.
- Rounded cards, buttons, navigation, assessment panels and modern dropdowns.
- Real Light/Dark switching through CustomTkinter appearance modes.
- Device and Problem Started dropdowns no longer use grey native ttk fields.
- Remove App automatically becomes Remove Apps when multiple apps are checked.
- Existing scanner, SQLite knowledge, repair outcomes and Shared Knowledge retained.
- Treeview remains ttk internally for fast 555-row inventory rendering, but is custom-themed.

## Icon pipeline
- Icon discovery remains restricted to CRITICAL/HIGH/CHECK apps.
- Added direct APK archive fallback for launcher PNG/WebP resources before adaptive XML parsing.
- APK path parsing made more tolerant.
- Existing icon cache retained.

LOCAL TEST ONLY — do not publish as a GitHub Release.
