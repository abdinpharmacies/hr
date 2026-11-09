# Customer locations — 19.0.1.12.0

Current changes before commit:
- Add reusable location cards and explicit draft-order delivery selection with provenance, stale-version checks, scoped server validation and audited selection/replacement/removal. Preserve unsaved drafts and existing address fields.
- Both Arabic catalogs are updated where source UI changes; existing translations and unrelated work are preserved.
- Validation and rollout requirements: `docs/customer-location-validation.md` at repository root. No live upgrade, restart or provider send.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-08-customer-locations.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/orders.py`
- `models/workspace.py`
- `static/src/location.js`
- `static/src/location.scss`
- `static/src/location.xml`
- `static/src/order_dialog.js`
- `static/src/order_dialog.xml`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/location.test.js`
- `tests/test_workspace.py`
