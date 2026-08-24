## fac9cfd9c5099fd1c49fbaaa42bf8c6376e27c51

- Author: hager yasser <hageryasser2002@gmail.com>
- Date: 2026-08-23T17:00:10+03:00
- Subject: ab_widgets/FEAT(#2188): Add Reusable Char Suggestions Widget to ab_widgets

User-facing changes:

- Added secure, reusable char-field suggestions from unique values in accessible previous records.
- Added recent-first filtering and a paginated Search More dialog.
- Added Arabic translations for the autocomplete interface.

Files changed:

- `ab_widgets/__init__.py`
- `ab_widgets/__manifest__.py`
- `ab_widgets/i18n/ar.po`
- `ab_widgets/i18n/ar_001.po`
- `ab_widgets/models/__init__.py`
- `ab_widgets/models/ab_char_autocomplete.py`
- `ab_widgets/static/src/ab_char_autocomplete.js`
- `ab_widgets/static/src/ab_char_autocomplete.scss`
- `ab_widgets/static/src/ab_char_autocomplete.xml`

## Current changes before commit

User-facing changes:

- Added static `data-ab-char-autocomplete="model.field"` activation for ordinary backend text inputs.
- Added an Odoo popover with recent unique suggestions, keyboard navigation, Search More, and native input event compatibility.
- Preserved free-form entry and the existing form-field char autocomplete widget.
- Fixed the autocomplete popover width rules so Odoo 19 libsass can compile the backend asset bundle.

Files changed:

- `ab_widgets/__manifest__.py`
- `ab_widgets/changelog.d/2026-08-23-generic-input-char-autocomplete.md`
- `ab_widgets/i18n/ar.po`
- `ab_widgets/i18n/ar_001.po`
- `ab_widgets/static/src/ab_char_autocomplete_input_service.js`
- `ab_widgets/static/src/ab_char_autocomplete.scss`
- `ab_widgets/static/src/ab_char_autocomplete.xml`
