# Module changelog

a6c12ec | Alhassan Hossny | 2026-09-30 | ab_accounting/Update: make x2many tables responsive inside form sheets

- Responsive accounting tables were added before the first-copy restoration.

Files changed:
- ab_accounting/__manifest__.py
- ab_accounting/static/src/scss/x2many_tables.scss
- ab_accounting/views/configuration.xml
- ab_accounting/views/journal.xml
- ab_accounting/views/opening.xml

Current changes before commit:

- Restore responsive journal-entry form tables with readable column widths and horizontal scrolling.
- Hide internal flag/header/balance columns using Odoo 19 column visibility in the embedded entry list.
- Use the standard Odoo 19 chatter so message tables no longer collapse the journal sheet.
- Scope table styles to the journal form while preserving the original fields and workflow.

- Fix startup report initialization using the Odoo 19 read-only query API and source dependencies.
- Replace the existing user-view XML ID to remove obsolete field references during upgrade.
- Verify the populated development schema on a snapshot before applying its targeted upgrade.
- Back up and upgrade rip_bconnect; preserve its journal values and verify normal startup and HTTP 200.

- Restore all 208 original accounting fields and the manual workflow from 389c000.
- Port views, ORM APIs, authorization, reporting and Excel entry to Odoo 19.
- Validate posting precision, balance, dimensions, account access, salary deductions and posted/frozen edits.
- Keep purchase integration external; retain only first-copy fields in the posting contract.
- Merge original and current Arabic catalogs and document isolated runtime checks.

Files changed:
- ab_accounting/static/src/scss/x2many_tables.scss
- ab_accounting/POSTING_CONTRACT.md
- ab_accounting/README.md
- ab_accounting/VALIDATION.md
- ab_accounting/__init__.py
- ab_accounting/__manifest__.py
- ab_accounting/data/account_guide.xml
- ab_accounting/data/allowed_fields.xml
- ab_accounting/data/doctype.xml
- ab_accounting/data/sequence.xml
- ab_accounting/i18n/ar.po
- ab_accounting/i18n/ar_001.po
- ab_accounting/models/__init__.py
- ab_accounting/models/ab_accounting_account_guide.py
- ab_accounting/models/ab_accounting_account_levels.py
- ab_accounting/models/ab_accounting_allowed_field.py
- ab_accounting/models/ab_accounting_doctype.py
- ab_accounting/models/ab_accounting_je_header.py
- ab_accounting/models/ab_accounting_je_header_delegate_common.py
- ab_accounting/models/ab_accounting_je_line.py
- ab_accounting/models/ab_accounting_je_line_common.py
- ab_accounting/models/ab_accounting_je_line_compute_balance.py
- ab_accounting/models/ab_accounting_je_line_qry.py
- ab_accounting/models/ab_accounting_je_res_header.py
- ab_accounting/models/ab_due_salaries_wizard.py
- ab_accounting/models/configuration.py
- ab_accounting/models/extra_funcs.py
- ab_accounting/models/journal.py
- ab_accounting/models/opening.py
- ab_accounting/models/reporting.py
- ab_accounting/models/res_users_inherit.py
- ab_accounting/models/user_uth.py
- ab_accounting/report/__init__.py
- ab_accounting/report/export.py
- ab_accounting/report/templates.xml
- ab_accounting/report_wizard/__init__.py
- ab_accounting/report_wizard/account_statement_view.xml
- ab_accounting/report_wizard/account_statement_wizard.py
- ab_accounting/report_wizard/export_xlsx.py
- ab_accounting/report_wizard/templates/pdf_account_statement.xml
- ab_accounting/report_wizard/templates/template_account_statement.xml
- ab_accounting/report_wizard/templates/template_due_salaries_details.xml
- ab_accounting/report_wizard/templates/xlsx_account_statement.xml
- ab_accounting/security/ir.model.access.csv
- ab_accounting/security/security_groups.xml
- ab_accounting/security/security_rules.xml
- ab_accounting/static/src/scss/x2many_tables.scss
- ab_accounting/views/ab_accounting_account_levels.xml
- ab_accounting/views/ab_accounting_auth_group.xml
- ab_accounting/views/ab_costcenter_deduction_forbidden.xml
- ab_accounting/views/ab_costcenter_deduction_month_prevented.xml
- ab_accounting/views/ab_due_salaries_wizard.xml
- ab_accounting/views/account_auth.xml
- ab_accounting/views/account_guide.xml
- ab_accounting/views/account_header.xml
- ab_accounting/views/configuration.xml
- ab_accounting/views/doctype.xml
- ab_accounting/views/journal.xml
- ab_accounting/views/journal_entries.xml
- ab_accounting/views/journal_entries_one2many.xml
- ab_accounting/views/journal_entries_qry.xml
- ab_accounting/views/menus.xml
- ab_accounting/views/opening.xml
- ab_accounting/views/reporting.xml
- ab_accounting/views/user_auth.xml
- ab_accounting/views/z_menus.xml
- ab_accounting/changelog.d
