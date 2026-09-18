# v1.2.14 Local Test — scanner/icon/UI polish

- Keeps the scan overlay open through suspicious-app icon extraction.
- Shows `Loading app icons… n/N` as part of scan progress.
- Repaints once after icon extraction instead of once per icon.
- Preserves selected package and App Assessment through icon/name/retriage refreshes.
- Replaces Windows emoji/symbol UI icons with supersampled vector-style PIL/CTkImage icons.
- Removes emoji from CRITICAL/HIGH/CHECK and repair-intelligence lines.
- Cleanup active state is red; other selected navigation remains blue.
- The iPhone Guy header PNG now has its connected near-black background made transparent,
  so it blends into the navy application header instead of appearing as a black box.
