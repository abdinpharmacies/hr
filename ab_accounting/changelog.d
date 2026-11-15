# Accounting changes

## Current changes before commit:

- Use Odoo 19 numeric date formatting throughout Accounting forms and lists, including embedded journal lines, inquiry screens, salary/deduction screens, and account-statement wizard ranges.
- Follow the active language's date format (YYYY-MM-DD when configured), retain timestamp times and existing field permissions, and override obsolete datepicker display options through module-owned inherited views.
- Load the numeric-date extensions after the existing views; keep shared frontend components, accounting values, report exports, and translations unchanged.
- Validate a fresh install and targeted upgrade in a disposable Odoo database, all 35 resolved date/timestamp occurrences, and 15 English/Arabic browser scenarios covering embedded dates, blanks, edit/save, wizard ranges, and retained timestamp times.

Files changed:
- `__manifest__.py`
- `changelog.d`
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

Files changed:
- `__manifest__.py`
- `changelog.d`
- `static/src/scss/x2many_tables.scss`
- `views/ab_due_salaries_wizard.xml`
- `views/account_header.xml`
- `views/journal_entries_one2many.xml`

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
