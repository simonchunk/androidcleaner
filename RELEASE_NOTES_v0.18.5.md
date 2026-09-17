# Android Cleaner v0.18.5

Updater reliability fix.

- Fixes GitHub update checks in the compiled Windows app by using a bundled, verified CA certificate bundle.
- Keeps TLS certificate verification enabled.
- Improves update-check error messages so connection, HTTP and certificate failures are visible.
- No database/schema changes. Existing workstation settings and learned knowledge are preserved.
