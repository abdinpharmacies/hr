# WhatsApp outgoing locations

## Committed baseline

- Commit: `60aef112bbae5214de2576aa9def6022178c4fb1`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:51:57+02:00`
- Original subject: `ab_crm_messaging/docs: record reception and receipt preview updates`

## Current changes before commit:

- Permit validated WhatsApp location evidence in immutable outgoing operations, retaining mixed-content rejection.
- Validation and rollout: [notification and branch location update](../../docs/simple-notifications-whatsapp-locations.md).

Files changed:

- `__manifest__.py`
- `models/location.py`
