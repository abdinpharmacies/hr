# WhatsApp reception, contacts and templates

## Committed baseline

- Commit: `efee2ce6389ec70c47d67d0d4ef7057c5f3e06ae`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:05:37+02:00
- Original subject: ab_crm_messaging/docs: record historical provenance update and validation

## Changes included in implementation commit `17051b0c`

- Add a provider-specific incoming-media validation extension point and private source/failure metadata.
- Accept optional WhatsApp event metadata without changing the Telegram event contract.

Validation and rollout evidence: `docs/whatsapp-reception-rollout.md`. Runtime rollout and live provider acceptance remain pending the user-managed maintenance window.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/media.py`
- `models/messaging.py`
