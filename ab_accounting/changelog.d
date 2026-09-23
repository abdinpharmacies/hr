Current changes before commit:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.
- Remove the web_domain_field manifest dependency; its purchase selector usage is replaced in ab_purchase.
- Recheck journal balances through ordinary iteration without a progress-addon method.

Files changed:

- ab_accounting/__manifest__.py
- ab_accounting/changelog.d
- ab_accounting/models/ab_accounting_je_header.py

Validation:

- Manifest metadata/data-file checks, Python parsing, and remaining dependency resolution passed without database or external-service access.
- AST comparison confirmed that progress-wrapper removal preserves loop bodies and surrounding behavior.
- No new or edited user-facing source strings; existing translation entries were preserved. Installation and UI validation remain pending the separate Odoo 19 port.

commit fc281808767bc0ab4bef6e741d364aa43c2bbcf1
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:55:11+03:00

    ab_accounting/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_accounting/__init__.py
- ab_accounting/__manifest__.py
- ab_accounting/data/account_guide.xml
- ab_accounting/data/allowed_fields.xml
- ab_accounting/data/create_xml_id_for_old_record.txt
- ab_accounting/data/doctype.xml
- ab_accounting/i18n/ar_001---.po
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
- ab_accounting/models/extra_funcs.py
- ab_accounting/models/old_data_query.py
- ab_accounting/models/res_users_inherit.py
- ab_accounting/models/user_uth.py
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
- ab_accounting/static/description/icon.png
- ab_accounting/static/src/js/archive_security.js
- ab_accounting/tests/__init__.py
- ab_accounting/tests/test_create_je.py
- ab_accounting/views/ab_accounting_account_levels.xml
- ab_accounting/views/ab_accounting_auth_group.xml
- ab_accounting/views/ab_costcenter_deduction_forbidden.xml
- ab_accounting/views/ab_costcenter_deduction_month_prevented.xml
- ab_accounting/views/ab_due_salaries_wizard.xml
- ab_accounting/views/account_auth.xml
- ab_accounting/views/account_guide.xml
- ab_accounting/views/account_header.xml
- ab_accounting/views/doctype.xml
- ab_accounting/views/journal_entries.xml
- ab_accounting/views/journal_entries_one2many.xml
- ab_accounting/views/journal_entries_qry.xml
- ab_accounting/views/user_auth.xml
- ab_accounting/views/z_menus.xml
