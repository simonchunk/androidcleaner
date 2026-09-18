# v1.2.15 Local Test — boot fix

Fixes the v1.2.14 startup crash:
`NameError: name 'ImageDraw' is not defined`

The new vector-style UI icon renderer introduced in v1.2.14 uses
`ImageDraw.Draw(...)`, but ImageDraw was not imported from Pillow.

No diagnostic, shared-knowledge, icon-extraction, or database logic was changed.
All v1.2.14 UI/icon/scanner changes are retained.
