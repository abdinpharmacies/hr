# Message-aware gateway eligibility

Current changes before commit:
- Version 19.0.1.4.1 adds an inheritable message eligibility check at approval and explicit retry, allowing the optional WhatsApp addon to validate approved templates and media without changing Telegram's default behavior.
- No source UI strings change; both Arabic catalogs remain intact.

Files changed:
- `__manifest__.py`
- `models/messaging.py`
- `changelog.d/2026-11-08-message-eligibility.md`
