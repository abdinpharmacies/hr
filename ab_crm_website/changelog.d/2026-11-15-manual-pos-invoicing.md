# Manual POS invoicing for Website orders

Current changes before commit:

- Keep incoming invoice cards and grouped customer conversations; remove their Create order button.
- Remove Website POS action/workspace overrides, draft product mapping preparation and POS quotation panel.
- Preserve the general contact/header POS workflow and readable invoice unit mappings.
- Retain existing drafts, invoices, immutable snapshots and historical handoff/progress metadata.
- Cover display-only English/Arabic cards, manual product entry, direct API payloads and preserved drafts.
- Keep native portal chat integration and two-message recovery suspended.

Files changed:

- `models/adapter.py`
- `static/src/order.xml`
- `static/src/order.scss`
- `static/src/pos.js` (removed)
- `static/src/workspace.js` (removed)
- `tests/test_adapter.py`
- `tests/test_pos.py`
- `tests/test_ui.py`
- `README.md`
- `changelog.d/2026-11-15-manual-pos-invoicing.md`
