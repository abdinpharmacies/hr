# Accounting changes

## Current changes before commit:

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
