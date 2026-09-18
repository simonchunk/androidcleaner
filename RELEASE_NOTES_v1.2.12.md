# v1.2.12 Local Test — Dark UI + real Android icons

## Fixes
- Defines APP_DIR from the packaged runtime BASE_DIR, fixing the icon pipeline NameError.
- Ensures icon-helper.jar is installed beside the application.
- Suspicious/review apps now attempt Android's own PackageManager-rendered icon first.
- Existing fallback/generic cached icons can be replaced by the real rendered icon.

## UI
- Dark mode is now the only/default appearance; light-mode toggle removed.
- Cleanup/Review/Games/Unused Apps/All Apps active tab uses bright blue selected treatment.
- Rescan is a prominent blue action.
- Larger 46 px app icons in the list.
- Selected app gets a dedicated ~118 px icon in the App assessment panel.
- CRITICAL/HIGH/CHECK risk text uses a boxed badge-style treatment.
- Existing row risk tinting and selected-row highlight retained.

Expected icon log:
ICON SERIAL ACCESSOR OK
ICON PIPELINE START
ICON PIPELINE QUEUE
ICON DEVICE ... helper found
ICON DEVICE ... app_process rc=...
ICON DEVICE ... pulled PNG
ICON PIPELINE RESULT ... loaded
