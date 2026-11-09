# Customer locations — 19.0.1.2.0

Current changes before commit:
- Record canonical incoming WhatsApp location history with the original identity and immutable message snapshot, retaining reception guards and the protected provider addon.
- Both Arabic catalogs are updated where source UI changes; existing translations and unrelated work are preserved.
- Validation and rollout requirements: `docs/customer-location-validation.md` at repository root. No live upgrade, restart or provider send.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-08-customer-locations.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/gateway.py`
- `models/history.py`
- `tests/test_bridge.py`
