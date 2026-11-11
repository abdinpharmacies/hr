## d13253a90ebae08cdecc4846ca7f38fdc9279a07

- Author: emadco88 <emadco88@gmail.com>
- Date: Wed Aug 19 11:02:49 2026 +0300
- Subject: ab_widgets/ FIX many2one selection

User-facing changes:

- Fixed AB many2one Search More selection so choosing a row keeps the selected record in the input.
- Reused the selected record id to read its display name when the Search More dialog returns id-only data.
- Passed the AB many2one `searchMoreLabel` option through to Odoo's autocomplete component.

Files changed:

- `ab_widgets/changelog.d/2026-08-19-ab-many2one-search-more.md`
- `ab_widgets/static/src/ab_many2one.js`

## Current changes before commit

User-facing changes:

- Added the opt-in `ab_char_autocomplete` widget for stored char fields.
- Added same-model, same-field distinct value suggestions using Odoo access rules without `sudo`.
- Added paginated Search More suggestions with Arabic translations.
- Added safer suggestion loading behavior for failed or stale asynchronous requests.

Files changed:

- `ab_widgets/__init__.py`
- `ab_widgets/__manifest__.py`
- `ab_widgets/changelog.d/2026-08-19-ab-many2one-search-more.md`
- `ab_widgets/i18n/ar.po`
- `ab_widgets/i18n/ar_001.po`
- `ab_widgets/models/__init__.py`
- `ab_widgets/models/ab_char_autocomplete.py`
- `ab_widgets/static/src/ab_char_autocomplete.js`
- `ab_widgets/static/src/ab_char_autocomplete.scss`
- `ab_widgets/static/src/ab_char_autocomplete.xml`
