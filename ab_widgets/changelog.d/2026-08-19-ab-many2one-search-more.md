## 3db5d596c9429ff082c3fe9b0466692b945f788f

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Jul 28 15:21:42 2026 +0300
- Subject: INIT commit pos19

User-facing changes:

- Added reusable AB many2one and many2many widgets for Odoo 19 frontend screens.
- Added autocomplete search behavior patches for AB widgets.
- Added keyboard mapping support for Arabic and English input in AB many2one searches.

Files changed:

- `ab_widgets/__init__.py`
- `ab_widgets/__manifest__.py`
- `ab_widgets/static/src/ab_many2many.js`
- `ab_widgets/static/src/ab_many2many.scss`
- `ab_widgets/static/src/ab_many2many.xml`
- `ab_widgets/static/src/ab_many2one.js`
- `ab_widgets/static/src/ab_many2one.scss`
- `ab_widgets/static/src/ab_many2one.xml`
- `ab_widgets/static/src/ab_many2one_keyboard_context_patch.js`
- `ab_widgets/static/src/ab_many2one_keyboard_context_patch.xml`
- `ab_widgets/static/src/ab_many2x_keyboard_map_patch.js`
- `ab_widgets/static/src/ab_many2x_patch.js`

## Current changes before commit

User-facing changes:

- Fixed AB many2one Search More selection so choosing a row keeps the selected record in the input.
- Reused the selected record id to read its display name when the Search More dialog returns id-only data.
- Passed the AB many2one `searchMoreLabel` option through to Odoo's autocomplete component.

Files changed:

- `ab_widgets/changelog.d/2026-08-19-ab-many2one-search-more.md`
- `ab_widgets/static/src/ab_many2one.js`
