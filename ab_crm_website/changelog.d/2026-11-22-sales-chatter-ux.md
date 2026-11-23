# Sales Chatter conversation UX

Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Group website orders into customer conversations while preserving original intake evidence.

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
- Reject ambiguous login handoffs that would claim unrelated legacy orders previously grouped by phone.
- Keep customer addresses readable when Arabic has not yet been activated.
- Separate Support session and order targets, histories, read positions, uploads and reply destinations.
- Use lifecycle evidence for centered departure information while preserving protected history.
- Add private employee archive preferences and immutable guest origin; group new orders by verified ownership rather than phone.
- Preserve account ownership during verified identity consolidation and maintain both Arabic catalogs.

Files changed:
- `ab_crm_website/README.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/controllers/adapter.py`
- `ab_crm_website/i18n/ar.po`
- `ab_crm_website/i18n/ar_001.po`
- `ab_crm_website/models/__init__.py`
- `ab_crm_website/models/adapter.py`
- `ab_crm_website/models/media.py`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/protocol.py`
- `ab_crm_website/security/ir.model.access.csv`
- `ab_crm_website/security/security.xml`
- `ab_crm_website/static/src/order.xml`
- `ab_crm_website/static/src/reply.js`
- `ab_crm_website/tests/__init__.py`
- `ab_crm_website/tests/test_chat_ux.py`
