# Accounting changes

## Current changes before commit:

<<<<<<< Updated upstream
<<<<<<< Updated upstream
- Use Odoo 19 numeric date formatting throughout Accounting forms and lists, including embedded journal lines, inquiry screens, salary/deduction screens, and account-statement wizard ranges.
- Follow the active language's date format (YYYY-MM-DD when configured), retain timestamp times and existing field permissions, and override obsolete datepicker display options through module-owned inherited views.
- Load the numeric-date extensions after the existing views; keep shared frontend components, accounting values, report exports, and translations unchanged.
- Validate a fresh install and targeted upgrade in a disposable Odoo database, all 35 resolved date/timestamp occurrences, and 15 English/Arabic browser scenarios covering embedded dates, blanks, edit/save, wizard ranges, and retained timestamp times.
=======
- Import journal clipboard rows using Odoo 19 relational lookups and validate blank, malformed, ambiguous, and invalid input before modifying lines.
- Enforce forbidden-branch access on journal headers, child lines, and statement query rows, including mixed-branch headers; retain administrator and Accounting Manager access.
- Apply the selected branch to account-statement opening balances.
- Maintain the new validation messages in both Arabic language files and repair the existing posted-entry translation newline.
>>>>>>> Stashed changes

Files changed:
- `models/ab_accounting_je_header.py`
- `models/res_users_inherit.py`
- `report_wizard/account_statement_wizard.py`
- `security/security_rules.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d`
<<<<<<< Updated upstream
- `views/numeric_date_views.xml`

## 43ec592eb — hossam elsheikh — 2026-11-12

Original commit subject: `ab_accounting/FIX: clean journal entry list and enable bulk editing`

- Clean journal entry list columns and enable bulk editing while retaining workflow conditions.

Files changed:
- `views/journal_entries.xml`

## 4aa80b1f9 — emadco88 — 2026-11-11

Original commit subject: `ab_accounting/ FIX views`

- Align journal header tables with the dev-central19 responsive layout while retaining the existing line widget and workflow controls.
- Use Odoo 19 list-view contexts, hide embedded technical columns, and modernize journal header chatter.
=======
- Import journal clipboard rows using Odoo 19 relational lookups and validate blank, malformed, ambiguous, and invalid input before modifying lines.
- Enforce forbidden-branch access on journal headers, child lines, and statement query rows, including mixed-branch headers; retain administrator and Accounting Manager access.
- Apply the selected branch to account-statement opening balances.
- Maintain the new validation messages in both Arabic language files and repair the existing posted-entry translation newline.
>>>>>>> Stashed changes

Files changed:
- `models/ab_accounting_je_header.py`
- `models/res_users_inherit.py`
- `report_wizard/account_statement_wizard.py`
- `security/security_rules.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d`
=======
>>>>>>> Stashed changes

## 43ec592e — hossam elsheikh — 2026-11-12

Original commit subject: `ab_accounting/FIX: clean journal entry list and enable bulk editing`

- Add cleaner journal-entry list variants and bulk editing controls.

Files changed:
- `views/journal_entries.xml`

## 0687472d3 — emadco88 — 2026-11-11

Original commit subject: `NEW INIT from dev-central19`

- Allow account and allowed-field authorizations to retain an empty authorization group during migration.
- Preserve required account/field references and existing permission defaults.

Files changed:
- `models/user_uth.py`
- `changelog.d`

## 43af83499 — emadco88 — 2026-11-09

Original commit subject: `migrate19 INIT`

- Initialize the Odoo 19 accounting addon.

Files changed:
- `__manifest__.py`
- `models/`
- `views/`
- `security/`

## Current changes before commit:

- Use the Odoo 19 account guide IDs for firing deductions and the due salaries journal test.

Files changed:
- `models/ab_accounting_je_line.py`
- `tests/test_create_je.py`
- `changelog.d`
