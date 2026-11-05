# Sales Chatter first release — 2026-11-05

Current changes before commit:

- Allow authorized PIN employees to share conversations without claiming; retain assignment history, order revisions and price auditing.
- Persist grouped employee/user/company/conversation alerts independently of read positions; acknowledge exact message snapshots and synchronize tabs.
- Focus customer messages after rendering, preserve composer/order drafts and older-history scroll, and restore signed-out backlogs.
- Normalize channel statuses with one timestamp/footer, safe failure explanations, protected provider diagnostics and bounded retries.
- Add scoped CRM contact search/create/edit/archive with local overrides, normalized-phone duplicate selection and protected employee audit records.
- Fix Customers and Messages/Notes inherited XML architectures under --dev=xml; add restricted Chatter Action Log views.
- Update both Arabic catalogs, regression coverage, runtime documentation and validation evidence.

Files changed:

- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/models/__init__.py`
- `ab_crm_sales_workspace/models/alerts.py`
- `ab_crm_sales_workspace/models/directory.py`
- `ab_crm_sales_workspace/models/orders.py`
- `ab_crm_sales_workspace/models/session.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/security/ir.model.access.csv`
- `ab_crm_sales_workspace/security/record_rules.xml`
- `ab_crm_sales_workspace/static/src/alerts.xml`
- `ab_crm_sales_workspace/static/src/contacts.js`
- `ab_crm_sales_workspace/static/src/contacts.xml`
- `ab_crm_sales_workspace/static/src/session_service.js`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/tests/test_workspace.py`
- `ab_crm_sales_workspace/views/views.xml`
- `ab_crm_sales_workspace/changelog.d/2026-11-05-first-release.md`

- `ab_crm_sales_workspace/VALIDATION.md`
