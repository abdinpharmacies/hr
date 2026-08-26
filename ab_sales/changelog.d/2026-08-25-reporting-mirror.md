## e75e30a5fa549a0d02a6759ac618bc866ddf5d51

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Tue Aug 25 10:56:40 2026 +0300
- Subject: ab_sales_sync: relax mirror identity fields

User-facing changes:

- Made mirror identity fields permissive for partial and out-of-order branch payloads.

Files changed:

- `ab_sales_sync/models/ab_sales_sync_models.py`
- `ab_sales_sync/changelog.d/2026-08-25-sync-model-required-fields.md`

## 8904f4900fab9e46a61437544b4fec68f6a9eed2

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Aug 25 18:12:17 2026 +0300
- Subject: ab_sales_sync/ FIX remove ab_sales as dependencies from ab_sales_sync

User-facing changes:

- Removed the operational Sales addon from the reporting mirror dependency chain.
- Added the master-data dependencies required by reporting relations.

Files changed:

- `ab_sales_sync/__manifest__.py`

## Current changes before commit:

User-facing changes:

- Converted `ab_sales` into a passive reporting addon using the original sales model names.
- Preserved branch isolation and replay audit data through `db_serial`, `rec_id`, raw payload, revision, event, source-user, operation, and timestamp fields.
- Kept the reporting models independent from the sync framework so `ab_sales` can be installed on its own.
- Replaced operational sales access and screens with manager-only, read-only reporting views.
- Removed operational E-Plus behavior, cron jobs, APIs, wizards, frontend assets, direct-print tooling, tests, and workflow constraints.
- Moved the sync profiles and mappings into the separate `ab_sales_sync` connector application.
- Added and validated Arabic translations for both `ar` and `ar_001`.

Files changed:

- `ab_sales/__manifest__.py`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_mirror_models.py`
- `ab_sales/security/groups_sales.xml`
- `ab_sales/security/rules_sales.xml`
- `ab_sales/security/ir.model.access.csv`
- `ab_sales/views/sales_mirror_views.xml`
- `ab_sales/views/sales_mirror_extra_views.xml`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- Removed obsolete operational runtime files under `ab_sales/models`, `data`, `views`, `static`, `tests`, `tools`, and `doc`.
