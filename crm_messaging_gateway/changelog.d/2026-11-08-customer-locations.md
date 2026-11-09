# Customer locations — 1.2.0

Current changes before commit:
- Normalize incoming Telegram locations/venues and WhatsApp locations. Validate finite bounded coordinates, preserve zero, bound optional text, fall back for malformed locations and ignore live-location edits.
- Both Arabic catalogs are updated where source UI changes; existing translations and unrelated work are preserved.
- Validation and rollout requirements: `docs/customer-location-validation.md` at repository root. No live upgrade, restart or provider send.

Files changed:
- `app/__init__.py`
- `app/providers.py`
- `changelog.d/2026-11-08-customer-locations.md`
- `tests/test_locations.py`
