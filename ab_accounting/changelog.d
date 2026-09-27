Current changes before commit:

Applied to the repository on 2026-09-27; targeted isolated upgrade and runtime verification passed.

- Port the standalone addon to Odoo 19 with Float-only, two-decimal journals and preserved journal/account hierarchy models.
- Link journal branches, items, periods, opening runs, reports and explicit user assignments directly to existing ab_store records; remove the separate accounting branch setup and show all active stores in selectors.
- Keep company scope on accounting records and preserve privilege-based roles, assigned-store posting and whole-journal authorization.
- Introduce atomic posting, canonical retry fingerprints, database identity uniqueness, coordinated period/opening locks and immutable posted financial data.
- Add audited review, full reversals, manual opening reconciliation and native posted-only financial reports with secured PDF/XLSX exports.
- Remove salary tools, custom spreadsheet entry, legacy helpers/import scripts, delegated journal scaffolding and the shared frontend patch.
- Retain company authorship, identify the current developer, maintain both Arabic catalogs, and document configuration, the adapter contract and isolated validation.
- Keep acceptance harnesses outside the production addon; 106 checks passed on the direct-store revision, with clean installation, targeted upgrades, concurrency, exports and runtime Arabic verification.
- Verify clean installation and targeted upgrade from the repository, independent company periods/openings on shared stores, concurrent posting/closure, and current Arabic translations; render README roles as a list compatible with Odoo module descriptions.

Files changed:

- ab_accounting/POSTING_CONTRACT.md
- ab_accounting/README.md
- ab_accounting/VALIDATION.md
- ab_accounting/__init__.py
- ab_accounting/__manifest__.py
- ab_accounting/changelog.d
- ab_accounting/data/account_guide.xml
- ab_accounting/data/allowed_fields.xml
- ab_accounting/data/create_xml_id_for_old_record.txt
- ab_accounting/data/doctype.xml
- ab_accounting/data/sequence.xml
- ab_accounting/i18n/ar.po
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
- ab_accounting/models/configuration.py
- ab_accounting/models/extra_funcs.py
- ab_accounting/models/journal.py
- ab_accounting/models/old_data_query.py
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

commit 575d6a9ffd068593cba767c7dd2505b382e50207
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:31:41+03:00

    ab_accounting/ FIX

- Standardize Odoo 19 manifest metadata and remove the web_domain_field dependency.
- Replace the progress-wrapper journal loop with ordinary iteration; full accounting compatibility remained pending.

Files changed:

- ab_accounting/__manifest__.py
- ab_accounting/changelog.d
- ab_accounting/models/ab_accounting_je_header.py
