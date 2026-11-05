# Chatter layout and separate Orders view — 2026-11-05

Current changes before commit:

- Match the WhatsApp dashboard proportions, full-height message area, contact previews, fixed composer and grouped controls; automatically select a conversation and scroll to its latest messages.
- Prefer customer/catalog/profile names and phone numbers over legacy Telegram destination IDs; remove employee assignment from conversation cards.
- Add Conversations and Orders child menus while retaining the existing Sales Chatter menu/action IDs. Orders opens the scoped POS-style editor with distinct draft labels.
- Preserve unsent composer and order drafts across view navigation, scoped by employee and company; retain server-side ownership and delivery restrictions.
- Translate new labels in both Arabic catalogs and add customer-label/access and menu regression coverage.

Files changed:

- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/views/views.xml`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/session_service.js`
- `ab_crm_sales_workspace/static/src/order_dialog.xml`
- `ab_crm_sales_workspace/static/src/order_dialog.scss`
- `ab_crm_sales_workspace/tests/test_workspace.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/VALIDATION.md`
- `ab_crm_sales_workspace/changelog.d/2026-11-05-sales-chatter-repair.md`
- `ab_crm_sales_workspace/changelog.d/2026-11-05-chatter-layout.md`
