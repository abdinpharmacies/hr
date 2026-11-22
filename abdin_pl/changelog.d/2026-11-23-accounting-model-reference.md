# Profit and loss accounting model reference — 2026-11-23

## Recent commit

- Commit: `43af83499b32d97266353b5333a887ed62d2d5a2`
- Author: emadco88
- Date: 2026-11-09T15:41:15+02:00
- Original commit subject: migrate19 INIT
- Added the profit and loss module to the Odoo 19 migration repository.

Files changed:

- `abdin_pl/__init__.py`
- `abdin_pl/__manifest__.py`
- `abdin_pl/controllers/__init__.py`
- `abdin_pl/controllers/connect_mssql.py`
- `abdin_pl/controllers/controllers.py`
- `abdin_pl/demo/demo.xml`
- `abdin_pl/hooks.py`
- `abdin_pl/models/__init__.py`
- `abdin_pl/models/abdin_pl.py`
- `abdin_pl/models/test.txt`
- `abdin_pl/security/ir.model.access.csv`
- `abdin_pl/security/security.xml`
- `abdin_pl/static/description/icon.png`
- `abdin_pl/views/cron_repl.xml`
- `abdin_pl/views/templates.xml`
- `abdin_pl/views/views.xml`

## Current changes before commit:

- Correct the document type ACL model reference to `ab_accounting_base.model_ab_accounting_doctype` so loading the access CSV does not depend on the legacy XML ID.
- Preserve ACL permissions, groups, and other references still owned by `ab_accounting`.
- No user-facing strings changed; Arabic and English translations require no updates.
- No tests, database operations, or backups performed, as requested.

Files changed:

- `abdin_pl/security/ir.model.access.csv`
- `abdin_pl/changelog.d/2026-11-23-accounting-model-reference.md`
