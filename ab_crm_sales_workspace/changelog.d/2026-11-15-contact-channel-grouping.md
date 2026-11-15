# Shared reviewed contact grouping

Current changes before commit:

- Support contact channel navigation for every configured messaging provider.
- Preview complete adapter-supplied conversation groups and confirm their links atomically with stale-state checks, access validation, manager-only conflict resolution and idempotent audits.
- Retain verified-phone matching only for Telegram/WhatsApp and guard direct association edits for other providers.
- Show affected conversations and current associations in English and Arabic.

Files changed:

- `models/customer_streams.py`
- `models/workspace.py`
- `static/src/contacts.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `__manifest__.py`
- `README.md`
- `changelog.d/2026-11-15-contact-channel-grouping.md`
