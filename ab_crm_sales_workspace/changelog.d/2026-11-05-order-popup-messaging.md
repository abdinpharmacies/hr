# Sales Chatter order popup and messaging — 2026-11-05

Current changes before commit:

- Open orders in a responsive POS-style dialog with explicit scoped branch selection, searchable units, product cards, delivery-only edits, guarded close and existing channel acceptance.
- Save draft changes atomically, reject stale editors, reprice branch changes with old/new line audits, refresh derived identity and retain accepted historical snapshots.
- Add private media composition/previews, recording cleanup, quoted replies, reactions, search, employee read history and manager-maintained branch/company saved replies.
- Identify owned shared contacts after claim or arrival without blocking reception; unify display names across inbox, heading and notifications.
- Keep all sales submission, contract, payment, invoice and stock operations outside this workflow.

- Update both Arabic catalogs and focused regression coverage.

Files changed:

- `ab_crm_sales_workspace/VALIDATION.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/changelog.d/2026-11-05-order-popup-messaging.md`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/models/__init__.py`
- `ab_crm_sales_workspace/models/orders.py`
- `ab_crm_sales_workspace/models/saved_reply.py`
- `ab_crm_sales_workspace/models/session.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/security/ir.model.access.csv`
- `ab_crm_sales_workspace/security/record_rules.xml`
- `ab_crm_sales_workspace/static/src/order_dialog.js`
- `ab_crm_sales_workspace/static/src/order_dialog.scss`
- `ab_crm_sales_workspace/static/src/order_dialog.xml`
- `ab_crm_sales_workspace/static/src/templates.js`
- `ab_crm_sales_workspace/static/src/templates.xml`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/tests/test_workspace.py`
