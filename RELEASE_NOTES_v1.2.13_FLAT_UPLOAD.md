# v1.2.13 Flat GitHub Upload

Same v1.2.13 application code and UI.

Repository upload change only:
- `tig_red_brand.png` is now in the repository root.
- No `assets` folder needs to be uploaded through GitHub.
- GitHub Actions creates `package/assets` during the Windows build and copies the PNG there.
- The installer still installs the artwork under the application's `assets` directory.
