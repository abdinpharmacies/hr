# Read receipts, channel loading and animation attachments

## Committed baseline

- Commit: `60aef112bbae5214de2576aa9def6022178c4fb1`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:51:57+02:00`
- Original subject: `ab_crm_messaging/docs: record reception and receipt preview updates`

## Current changes before commit:

- Add an administrator-only, default-off WhatsApp read-receipt setting and an immutable durable receipt outbox.
- Authenticate leases/results by service account, branch and company; fence stale leases and keep acceptance separate from unread positions.
- Validate and retain original GIF and MP4 media in the shared addon, independent of the WhatsApp companion.
- Update both Arabic catalogs and shared media/security regression tests.
- Preserve the existing uncommitted contact, notification and branch-location changes recorded in their separate entries.

Files changed:

- `__manifest__.py`
- `changelog.d/2026-11-11-contact-audio-recovery.md`
- `changelog.d/2026-11-11-whatsapp-branch-locations.md`
- `controllers/gateway.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/animation.py`
- `models/location.py`
- `models/media.py`
- `models/read_receipts.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `tests/test_messaging.py`
- `views/views.xml`
- `changelog.d/2026-11-11-read-receipts-channel-loading-animations.md`
