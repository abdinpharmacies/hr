# Customer locations — 19.0.1.5.0

Current changes before commit:
- Validate incoming locations and retain immutable point/timestamp snapshots, with readable search/preview text and unchanged duplicate identity checks.
- Both Arabic catalogs are updated where source UI changes; existing translations and unrelated work are preserved.
- Validation and rollout requirements: `docs/customer-location-validation.md` at repository root. No live upgrade, restart or provider send.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-08-customer-locations.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/location.py`
- `models/messaging.py`
- `tests/test_messaging.py`
