# Unified contacts and open reception

## Committed baseline

- Commit: `efee2ce6389ec70c47d67d0d4ef7057c5f3e06ae`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_messaging/docs: record historical provenance update and validation`

## Changes included in implementation commit `17051b0c`

- Accept bounded opaque WhatsApp inbound identifiers independently of outgoing destination validation.
- Make archived conversations accessible again when a new signed event arrives.
- Retain the existing media, provenance and unsupported-attachment improvements.

Validation and rollout: `docs/unified-contacts-rollout.md`. Live rollout completed during the user-managed maintenance window; verification and remaining unmatched historical status evidence are recorded in the rollout document.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `changelog.d/2026-11-10-unified-contacts.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/media.py`
- `models/messaging.py`
