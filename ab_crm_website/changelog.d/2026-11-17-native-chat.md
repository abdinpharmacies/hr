# Website native chat

Baseline: 149fb44e — Alhassan Hossny — 2026-11-17 — ab_crm_website/feat: group orders into receive-only customer conversations

Current changes before commit:
- Add v2 order/general-support chat receipts with account, branch and company isolation.
- Queue validated text replies with immutable typed destinations, latest-customer-message routing and deliberate grouped-order selection.
- Keep historical replies blocked; separate source streams after contact linking; preserve invoice/manual POS behavior.
- Add English desktop/Arabic mobile and direct ORM/queue regression coverage; maintain both Arabic catalogs.

Files changed:
- `ab_crm_website/README.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/changelog.d/2026-11-17-native-chat.md`
- `ab_crm_website/controllers/adapter.py`
- `ab_crm_website/i18n/ar.po`
- `ab_crm_website/i18n/ar_001.po`
- `ab_crm_website/models/__init__.py`
- `ab_crm_website/models/adapter.py`
- `ab_crm_website/models/chat.py`
- `ab_crm_website/protocol.py`
- `ab_crm_website/security/ir.model.access.csv`
- `ab_crm_website/security/security.xml`
- `ab_crm_website/static/src/order.xml`
- `ab_crm_website/static/src/reply.js`
- `ab_crm_website/tests/test_contact_groups.py`
