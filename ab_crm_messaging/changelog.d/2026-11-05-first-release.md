# Sales Chatter first release — 2026-11-05

Current changes before commit:

- Keep provider diagnostic history reads scoped to already-authorized cancellation/retry operations when workspace field restrictions are installed.
- Restrict delivery diagnostic navigation and message evidence relations to CRM managers and administrators.
- Prevent delayed Telegram failure callbacks from downgrading confirmed Sent messages; retain authenticated WhatsApp failure receipts and monotonic delivery/read ordering.
- Extend replay/status regression coverage without changing integration switches or initiating sends.

Files changed:

- `ab_crm_messaging/__manifest__.py`
- `ab_crm_messaging/models/messaging.py`
- `ab_crm_messaging/tests/test_messaging.py`
- `ab_crm_messaging/views/views.xml`
- `ab_crm_messaging/changelog.d/2026-11-05-first-release.md`
