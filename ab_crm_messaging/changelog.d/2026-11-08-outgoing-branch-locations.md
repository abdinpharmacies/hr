# Outgoing location evidence — 19.0.1.6.0

Current changes before commit:
- Carry frozen outgoing Telegram venues in durable operation content, rejecting incompatible location/media/reaction/contact payloads.
- Keep queued content and location snapshots immutable; authenticated delivery reporting may attach the provider receipt once without rewriting the point.
- Retain incoming location validation and existing acknowledgement, failed-send retry and uncertain-delivery workflows.
- Validation and staged rollout: `docs/telegram-branch-location-validation.md` at repository root.

Files changed:
- `__manifest__.py`
- `models/location.py`
- `changelog.d/2026-11-08-outgoing-branch-locations.md`
