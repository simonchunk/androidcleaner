# Android Cleaner v1.2.30-rc1

Release candidate focused on workshop speed and device information.

- Master Scan is no longer held up by icons or app-name discovery.
- Icons are cached permanently by package and missing icons stay as placeholders rather than triggering slow fallback extraction.
- Android app labels are read natively in one background batch, improving OEM/OPPO labels such as #Contacts and #Messages.
- Added Android battery information, including health/cycles where the device exposes reliable values.
- Added a one-time What's New screen after updating and a rolling CHANGELOG.md.
