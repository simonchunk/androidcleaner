# v0.14.0

## Discovery-set resolver
The initial scan now resolves a bounded set of recent/post-baseline user apps, sideloads, active-special-access apps and package-hint matches before final triage. This is discovery only and never classifies an app by itself. It closes the gap where a random package name can hide a label such as Smart Clean Pro. The bulk setup/migration cluster is excluded and discovery is capped at 100 apps.


## Relevant-name pre-resolution and dynamic Cleanup resolution

- Fixes the detection hole where a newly installed cleaner/booster/etc. could be missed because its package name was not enough to classify it and its real Android label was never resolved.
- Adds a cheap package-name prefilter used **only** to decide which APK labels are worth resolving. A prefilter hit is not a malware/suspicious verdict and does not enter Cleanup by itself.
- After AAPT2 resolves a label, triage automatically runs again so the real app name can activate the normal Cleaner / QR / PDF / launcher / recovery category rules.
- Changing **Problem started** now re-triages and automatically resolves any newly visible Cleanup apps.
- Popup Ad Risk and Unused Apps keep the same automatic visible-name resolution behaviour.
- Guided Repair Outcome and solo/group repair intelligence from v0.13.3 are unchanged.

# The iPhone Guy Android Cleaner v0.10.8

Store workflow / sideload pass.

- Unknown SIDELOADED user apps now enter Cleanup as CHECK.
- Sideloaded does not mean malware; it is technician-review evidence only.
- Learned Safe/KNOWN SAFE sideloads remain suppressed.
- Device list is polled automatically.
- When exactly one new authorised device is detected, old phone results,
  selections, counters, model text and baseline are cleared immediately and
  the new phone is scanned automatically.
- If a phone is unplugged, stale results are cleared.
- If multiple authorised phones are connected, the app does not guess; staff
  select the required device.
- A scan-generation guard prevents a slow scan from an unplugged/previous phone
  publishing stale results after the device changes.
- Manual Refresh Devices still works.
- No DB schema migration. Existing local knowledge DB is preserved.

## v0.12.0 - Workshop UI refresh + startup fix
- New workshop-first main screen: connect, automatic scan, review findings, classify/remove, record outcome.
- Advanced views, resolver/logs, knowledge DB and online reputation tools moved under Advanced.
- Added How to Connect guide with Samsung, Pixel/general Android, USB debugging, Samsung Auto Blocker guidance, and finish/restore-security checklist.
- Learned KNOWN SAFE reputation now suppresses heuristic priority even when the legacy local reputation row is absent (important after knowledge DB import/sync).
- Existing LocalAppData knowledge database and migration/backups are unchanged; upgrading the ZIP does not reset learned data.


## v0.12.0 diagnostic triage
- Richer technician-facing evidence in **Why it is shown**.
- High-risk workshop categories use resolved app labels first and conservative package hints second.
- Reported problem timing now has stronger weight for installs and updates.
- Correlated evidence (timing + category/sideload, or sideload + powerful access) is elevated.
- Known Safe still overrides heuristic review signals; exact malware evidence remains the exception.


## v0.12.7 popup-ad signal tuning

Popup-ad risk now separates active access from merely declared manifest capability. Active draw-over-apps is HIGH; Accessibility becomes HIGH when correlated with popup capability or a high-risk category; notification-listener access requires correlation for MEDIUM. A single declared overlay or full-screen permission is no longer surfaced as Medium. This reduces false positives while preserving diagnostic Cleanup rules.


## v0.12.7 Popup Ad Risk view
- Adds a dedicated **Popup Ad Risk** workshop view beside Cleanup.
- Shows only user/OEM-app rows with HIGH, MEDIUM or LOW popup-ad evidence.
- Sorts HIGH -> MEDIUM -> LOW, then by supporting evidence and triage score.
- Selecting a row shows the exact popup-risk reasons in the assessment strip.
- The view is diagnostic only: it does not change malware reputation or cause an app to enter Cleanup.
- Cleanup and Unused Apps remain separate workflows.


## v0.13.3 automatic view name resolution

- Cleanup, Popup Ad Risk, and Unused Apps now automatically resolve the Android application labels for the apps displayed in that view.
- Resolved labels and SHA-256 identities continue to use the persistent identity cache, so previously seen package/version combinations do not need to be pulled again.
- All Apps remains non-automatic to avoid pulling hundreds of APKs during normal workshop use.
- Apps for which AAPT2 genuinely reports no application label are not repeatedly retried merely by changing views; Retry Name Errors remains available under Advanced for manual retries.


## v0.13.3
- Fixed Remove Selected multi-select: uninstall now uses all checked apps rather than only the blue focused Treeview row.
- Multi-app removals remain one repair group so a single Repair Outcome can be recorded for the selected removal batch.


## v0.14.0
- Fixes the Smart Clean Pro discovery hole: every genuine user-app install from the last 14 days is now a mandatory name-resolution candidate and cannot be crowded out by the discovery cap.
- Problem-started windows now use **first install time** for timing-only Cleanup findings.
- Play Store/app updates no longer pull otherwise ordinary old apps into Cleanup. Recent update time is supporting evidence only when another independent concern already exists.

## v0.14.0 — Intelligence presentation
- Replaced the buried single-line selected-app history with a bounded App assessment panel.
- Shows priority, reputation, technician decision, knowledge source, seen/removed counts, solo outcomes, group-associated outcomes, and pop-up-ad repair outcomes separately.
- Keeps classification separate from repair evidence: group success does not become proof against every app in the group.
- Cleanup/Popup/Unused name resolution remains automatic; final Cleanup candidates are queued for resolution after retriage. AAPT2 `No label` remains a package-name fallback rather than a false resolved label.

## v0.15.2 workflow cleanup
- Removed technician Malware and Suspicious buttons from the everyday workflow. Negative intelligence now comes from Repair Outcome.
- Kept a single Mark Safe override for known-good apps that should not appear in Cleanup.
- Removed MalwareBazaar controls from the normal UI. Existing cache/plumbing is left dormant for compatibility.
- Removed the Popup Ad Risk view. Popup/overlay/accessibility evidence remains available internally to Cleanup and App Assessment.
- Added a Games view as a separate secondary-cleanup pass. Being a game never makes an app suspicious by itself; games can still enter Cleanup when they independently trigger normal cleanup rules.
- Main secondary-cleanup summary now reports unused apps and games instead of popup-risk counts.


## v0.15.2 Cross-PC Test Mode
Advanced > Cross-PC Test Mode creates a separate fresh local database, downloads shared intelligence only as TEST-PC-2, blocks all shared uploads, rescans the connected phone against shared knowledge, and restores the normal local database when Test Mode is ended.

## v0.17.1 workshop changes
- Cleanup now contains CRITICAL/HIGH only. CHECK findings live in a separate Review tab.
- Repair Outcome is no longer a normal footer action: successful uninstall -> rescan -> Repair Outcome remains automatic. Manual outcome entry is available under Advanced for edge cases.
- Shared Knowledge malware lookup remains package-first, with a conservative exact resolved-app-name fallback for a unique KNOWN MALWARE record. This fixes package-variant cross-PC recognition such as Smart Clean Pro without using name-only matches to mark apps Safe.

## v0.17.1 production architecture preview
- Decision is removed from the workshop table; Reputation now occupies the prominent second evidence column after Review.
- Shared Knowledge sync is production-oriented: local evidence uploads, then shared intelligence downloads; it is rate-limited and also runs when a new device is connected.
- First-run configuration names the store and PC and creates a unique Store ID. The deployed Apps Script URL can be preloaded in `production_config.json`; the API key can also be injected there for the final installer build.
- Android Platform Tools and Build Tools remain automatically downloaded by SETUP for development ZIP builds. The final Windows installer will own this dependency bootstrap.
- Update infrastructure is scaffolded through `update_manifest_url`; no production manifest is published yet, so Check for Updates reports that cleanly.
- Local knowledge/configuration remain under LocalAppData and are not shipped inside this ZIP.

## v0.17.1 staff lockdown
- Everyday staff screen remains focused on Cleanup, Review, Games, Unused Apps and All Apps.
- Advanced tools are locked behind a company Admin PIN.
- Admin Mode unlocks diagnostics, Shared Knowledge configuration, database import/export, Cross-PC Test Mode and manual repair-intelligence tools for 15 minutes.
- The Admin PIN is compiled as a PBKDF2-SHA256 hash; the plaintext PIN is not stored by the application.
- First-run setup asks only for Store and Computer name; it does not ask staff to create an admin PIN.

## v0.17.3 - GitHub update channel

Android Cleaner now checks GitHub Releases from `simonchunk/androidcleaner`.

- Staff can use **Advanced > Check for Updates** without the Admin PIN.
- PCs default to the **Production** channel.
- Admin Mode can change a PC to **Test** via **Update Channel (Production/Test)**.
- Production uses GitHub's latest non-prerelease release.
- Test uses the newest non-draft release, including prereleases.
- Release notes come from the GitHub Release body.
- Put `[required]` anywhere in the release notes to mark the release as required in the Cleaner prompt.
- Attach a Windows `.exe` installer to the release for production deployment.
- Attach either `<installer-name>.sha256` or `sha256sums.txt` containing the installer's SHA-256. A verified EXE can be launched directly by the Cleaner. An unverified executable is downloaded but will not be run automatically.

### Publishing an update

1. Test the build on a PC using the Test channel.
2. In GitHub, create a Release with a version tag such as `v1.0.1`.
3. For Test builds, tick **Set as a pre-release**.
4. Attach the installer and its SHA-256 file.
5. When approved for stores, publish a normal non-prerelease Release. Production PCs will detect it automatically at startup, or staff can use **Check for Updates**.


## v0.17.3 Test Release
Visible GitHub updater end-to-end test build. Application title/version reports v0.17.3. No database schema changes.


## v0.17.4 - Production configuration
- Shared Knowledge Apps Script URL and deployment API credential are preloaded through production_config.json.
- First-run setup now only needs Store and Computer name for a normal deployment.
- Existing LocalAppData settings are preserved and are not overwritten by deploy-time defaults.
- GitHub Test/Production update channels from v0.17.3 are unchanged.
