# Clear stale media failure after recovery

## Committed baseline

- Commit: `60aef112bbae5214de2576aa9def6022178c4fb1`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:51:57+02:00`
- Original subject: `ab_crm_messaging/docs: record reception and receipt preview updates`

## Current changes before commit:

- Clear the previous failure reason when authenticated media recovery succeeds. Retain immutable ready-media bytes and existing account/branch/company checks.
- Preserve the preceding notification and branch-location updates.

Files changed:

- `__manifest__.py`
- `models/media.py`
- `tests/test_messaging.py`
