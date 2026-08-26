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

## b60d10b6a42633010ba74079a7df219d4cd8d47e

- Author: emadco88 <emadco88@gmail.com>
- Date: 2026-08-24T14:30:41+03:00
- Subject: ab_widgets/ UPD add to <input/> too

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

## Current changes before commit

User-facing changes:

- Polished the char autocomplete dropdown with a clearer elevated surface, wider readable popover, stronger hover/focus/active states, and bilingual text handling.
- Made Search More visually distinct from suggestion results while preserving the same click behavior.
- Redesigned the Suggestions dialog into a more modern SaaS search/select surface with a custom modal shell, refined header chrome, cohesive search control, quieter footer, cleaner result surface, and polished loading and empty states.
- Reduced the Suggestions dialog pagination footprint and hid the controls when there is only one result page.
- Kept the inline autocomplete popover visually anchored below the input field instead of flipping above it.
- Added a subtle directional Suggestions dialog result transition for Next and Previous pagination, with reduced-motion support.
- Added the same subtle result-enter transition to inline autocomplete suggestions after typing.
- Matched Suggestions dialog row hover and focus feedback to the inline autocomplete active accent treatment.
- Added debounced auto-search inside the reusable Suggestions dialog so typing refreshes results without pressing Search.
- Removed the Suggestions dialog Search button and kept the result list stable while auto-search requests are in flight to avoid visual jitter.
- Reserved a consistent Suggestions dialog results height so the modal does not resize when searches return fewer rows.
- Added a reusable autocomplete source registry in `ab_widgets`, with core detection for doctor specialty inputs so consumers do not need custom XML hooks.
- Added Arabic translations for the new helper and empty-state guidance text.

Files changed:

- `ab_widgets/changelog.d/2026-08-23-generic-input-char-autocomplete.md`
- `ab_widgets/i18n/ar.po`
- `ab_widgets/i18n/ar_001.po`
- `ab_widgets/static/src/ab_char_autocomplete.js`
- `ab_widgets/static/src/ab_char_autocomplete.scss`
- `ab_widgets/static/src/ab_char_autocomplete.xml`
- `ab_widgets/static/src/ab_char_autocomplete_input_service.js`
