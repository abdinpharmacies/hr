# Module update committed — 52ff214c

- Commit: `52ff214c5abf6badcbb3592c46f1b929c8f40938`
- Author: Alhassan Hossny
- Date: 2026-11-09T10:25:52+02:00
- Original subject: ab_crm_messaging/feat: support locations, Telegram edits and attachments

Preserve location and edit evidence, expand incoming attachment handling, and expose message eligibility and gateway capabilities.

Validation: 30 messaging tests passed on an isolated core-only database; both Arabic catalogs pass format checks.

Files changed:
- `__manifest__.py`
- `controllers/gateway.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/edits.py`
- `models/location.py`
- `models/media.py`
- `models/messaging.py`
- `tests/test_controller.py`
- `tests/test_messaging.py`
