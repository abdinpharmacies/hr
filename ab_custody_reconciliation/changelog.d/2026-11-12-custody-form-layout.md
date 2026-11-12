# ab_custody_reconciliation

## 43af8349 — emadco88 — 2026-11-09

Original commit subject: migrate19 INIT

- Imported the custody reconciliation module and its existing reconciliation, detail, approval, and notes screens.

Files changed:

- `ab_custody_reconciliation/__init__.py`
- `ab_custody_reconciliation/__manifest__.py`
- `ab_custody_reconciliation/data/custody_channel.xml`
- `ab_custody_reconciliation/data/template_custody_reconciliation_email.xml`
- `ab_custody_reconciliation/i18n/ar_001.po`
- `ab_custody_reconciliation/models/__init__.py`
- `ab_custody_reconciliation/models/ab_accounting_je_header_inherit.py`
- `ab_custody_reconciliation/models/ab_custody_reconciliation_header.py`
- `ab_custody_reconciliation/models/ab_custody_reconciliation_line.py`
- `ab_custody_reconciliation/models/ab_custody_reconciliation_wizard.py`
- `ab_custody_reconciliation/models/ab_reconciliation_employee_approval.py`
- `ab_custody_reconciliation/models/tafkit.py`
- `ab_custody_reconciliation/report_wizard/template_custody_settlement.xml`
- `ab_custody_reconciliation/security/ir.model.access.csv`
- `ab_custody_reconciliation/security/record_rules_approval.xml`
- `ab_custody_reconciliation/security/record_rules_reconciliation.xml`
- `ab_custody_reconciliation/security/security_groups.xml`
- `ab_custody_reconciliation/static/description/icon.png`
- `ab_custody_reconciliation/views/ab_accounting_je_header_inherit.xml`
- `ab_custody_reconciliation/views/ab_custody_reconciliation_header.xml`
- `ab_custody_reconciliation/views/ab_custody_reconciliation_line.xml`
- `ab_custody_reconciliation/views/ab_custody_reconciliation_wizard.xml`
- `ab_custody_reconciliation/views/ab_reconciliation_employee_approval.xml`
- `ab_custody_reconciliation/views/menus.xml`

## Current changes before commit:

- Align reconciliation totals, expand attachments, and move the print toggle out of the crowded action header.
- Remove excessive Submit button spacing, separate the detail filter from its table, and use the native Odoo 19 chatter.
- Arrange reconciliation details and approval configuration into balanced columns and keep wizard notes at the available width.
- Preserve business attributes, button methods, workflow conditions, domains, and contexts through inherited XML views.

Files changed:

- `ab_custody_reconciliation/views/ab_custody_reconciliation_header.xml`
- `ab_custody_reconciliation/views/ab_custody_reconciliation_line.xml`
- `ab_custody_reconciliation/views/ab_custody_reconciliation_wizard.xml`
- `ab_custody_reconciliation/views/ab_reconciliation_employee_approval.xml`
- `ab_custody_reconciliation/changelog.d/2026-11-12-custody-form-layout.md`

Validation:

- Targeted custody-module upgrades completed successfully; no Python, model, manifest, security, or business-logic files were edited.
- Static inheritance and business-attribute comparisons cover all eight forms and the optional HR employee-account extension.
- Odoo runtime checks resolve all eight forms in en_US and ar_001; the request and reconciliation forms retain language-specific translated content. The custody journal-entry extension resolves successfully.
- The restored database has no custody records and no authorized reconciliation users for record-level checks; reconciliation view checks used the existing superuser context. No business records or user permissions were changed for verification.
- Existing labels and translation files are unchanged; the added inherited views introduce no new user-facing strings.
- Browser visual verification is unavailable in this session.
