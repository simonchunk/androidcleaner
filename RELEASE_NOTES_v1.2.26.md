# Android Cleaner v1.2.26 — Master Scan

## Workshop change
- Removed the **Problem started** time-period control entirely.
- Every device now uses one **Master Scan**.
- First-install and last-update dates remain visible as technician context but contribute **zero risk score**.
- Install timing, recent updates, post-migration timing and onset-window correlation can no longer create or promote CHECK/HIGH/CRITICAL findings.
- Cleanup/Review now require independent evidence: learned/shared reputation, configured suspicious categories/naming, explicit sideload provenance, active powerful access, or other existing non-timing rules.
- Store provenance remains context only: Google Play/Galaxy Store does not automatically make an app safe or suspicious.

## Expected result
A normal app such as AGL must not be shown merely because it was installed around a possible problem period. It will only surface if another independent rule actually applies.

## Preserved
- v1.2.25 Drivers & Connection tools.
- v1.2.24 hard shutdown / ADB cleanup.
- v1.2.22 provenance fix and v1.2.21 protected-profile handling.
- Existing local/shared knowledge, repair intelligence, system/OEM protection and removal workflow.
