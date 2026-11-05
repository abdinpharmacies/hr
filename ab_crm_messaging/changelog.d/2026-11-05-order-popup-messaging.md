# Sales Chatter order popup and messaging — 2026-11-05

Current changes before commit:

- Extend normalized events and immutable outgoing content with private media, quoted references and reactions.
- Add account/company/conversation media authorization, byte/type/size limits, controlled worker transfer and explicit media failure evidence.
- Add default-off outgoing/automation controls and audited cancellation restricted to never-leased, never-submitted queued operations.

- Update both Arabic catalogs and focused regression coverage.

Files changed:

- `ab_crm_messaging/__manifest__.py`
- `ab_crm_messaging/changelog.d/2026-11-05-order-popup-messaging.md`
- `ab_crm_messaging/controllers/gateway.py`
- `ab_crm_messaging/i18n/ar.po`
- `ab_crm_messaging/i18n/ar_001.po`
- `ab_crm_messaging/models/__init__.py`
- `ab_crm_messaging/models/media.py`
- `ab_crm_messaging/models/messaging.py`
- `ab_crm_messaging/security/ir.model.access.csv`
- `ab_crm_messaging/security/record_rules.xml`
- `ab_crm_messaging/tests/test_messaging.py`
- `ab_crm_messaging/views/views.xml`
