# Shared callcenter conversations

Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Preserve the existing provider integration and reply hooks.

Files changed:
- `ab_crm_website/README.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/changelog.d/2026-11-16-customer-conversations.md`
- `ab_crm_website/changelog.d/2026-11-16-link-candidate-locks.md`
- `ab_crm_website/changelog.d/2026-11-16-receive-only.md`
- `ab_crm_website/i18n/ar.po`
- `ab_crm_website/i18n/ar_001.po`
- `ab_crm_website/models/adapter.py`
- `ab_crm_website/security/ir.model.access.csv`
- `ab_crm_website/security/security.xml`
- `ab_crm_website/static/src/order.xml`
- `ab_crm_website/tests/contact_group_concurrency.py`
- `ab_crm_website/tests/test_adapter.py`
- `ab_crm_website/tests/test_contact_groups.py`
- `ab_crm_website/tests/test_pos.py`

Current changes before commit:
- Remove reservation status from website details and keep reply availability based on access and destination state.
- Remove tab ownership metadata from composer uploads; preserve private drafts, upload ownership and target validation.
- Validate shared replies for distinct users and employees sharing an Odoo login.

Files changed:
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/controllers/adapter.py`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/static/src/reply.js`
- `ab_crm_website/tests/test_chat_ux.py`
