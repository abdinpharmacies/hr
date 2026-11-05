# Telegram contact sharing

Current changes before commit:

- Retain gateway contact phone/ownership evidence with protected ORM fields.
- Add explicit contact requests through the existing durable outgoing approval workflow.
- Include the localized Share contact keyboard in leased Telegram operations.
- Preserve Telegram provider ownership and existing channel/account mapping behavior.

Files changed:

- `__manifest__.py`
- `models/account.py`
- `i18n/ar.po`, `i18n/ar_001.po`
- `changelog.d/2026-11-04-contact-sharing.md`
