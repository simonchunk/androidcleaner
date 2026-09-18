# v1.2.6 local test — icon pipeline fix

- Fixes Windows `CREATE_NO_WINDOW` NameError in AAPT2 icon fallback.
- Adds explicit logging for the on-device IconFetcher pipeline: helper discovery, push, app_process execution, remote PNG size, pull, validation and cache.
- Verifies/re-pushes the helper if `/data/local/tmp` was cleared.
- Keeps Android framework rendering as the primary icon method and APK/AAPT2 extraction only as fallback.
