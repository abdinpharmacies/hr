# Channel-order interface and CRM contact repair — 2026-11-05

Current changes before commit:

- Use a separate Orders action under Sales Chatter and use an icon composer with server-derived disabled reasons, attachment/recording previews, keyboard sending and failure-safe drafts.
- Reuse the POS product card and many-to-one selector through channel-order adapters; add draft switching, keyboard quantities, barcode lookup, window controls and draft cancellation without sales persistence.
- Resolve self-shared contacts during authenticated ingestion in the account company/store scope, retain ambiguous matches for CRM manager review, and remove customer-linking writes from chat-detail reads.
- Separate phone/catalog verification from customer order approval, preserve accepted snapshots and agent delivery edits, and retain branch repricing, stale-editor rejection and price audits.
- Expose identification evidence and staff reads in existing CRM views, preserve CRM/OMS navigation and model ownership, and isolate in-memory drafts by employee across re-authentication.
- Update both Arabic catalogs and add eight focused backend regression tests.

Files changed:

- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/VALIDATION.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/models/orders.py`
- `ab_crm_sales_workspace/models/session.py`
- `ab_crm_sales_workspace/views/views.xml`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/order_dialog.js`
- `ab_crm_sales_workspace/static/src/order_dialog.xml`
- `ab_crm_sales_workspace/static/src/order_dialog.scss`
- `ab_crm_sales_workspace/tests/test_workspace.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/changelog.d/2026-11-05-sales-chatter-repair.md`
