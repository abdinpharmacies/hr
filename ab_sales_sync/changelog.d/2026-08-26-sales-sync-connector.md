## 8904f4900fab9e46a61437544b4fec68f6a9eed2

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Aug 25 18:12:17 2026 +0300
- Subject: ab_sales_sync/ FIX remove ab_sales as dependencies from ab_sales_sync

User-facing changes:

- Removed the operational Sales addon from the former mirror dependency chain.
- Added the master-data dependencies required by reporting relations.

Files changed:

- `ab_sales_sync/__manifest__.py`

## e75e30a5fa549a0d02a6759ac618bc866ddf5d51

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Tue Aug 25 10:56:40 2026 +0300
- Subject: ab_sales_sync: relax mirror identity fields

User-facing changes:

- Made mirror identity fields permissive for partial and out-of-order branch payloads.

Files changed:

- `ab_sales_sync/models/ab_sales_sync_models.py`
- `ab_sales_sync/changelog.d/2026-08-25-sync-model-required-fields.md`

## Current changes before commit:

User-facing changes:

- Connected the manually installed sales connector to the report-only
  `ab_odoo_sync_mapping` runtime and the passive `ab_sales` models.
- Preserved all 14 same-name `mirror_sync` profiles and their field mappings.

Files changed:

- `ab_sales_sync/__init__.py`
- `ab_sales_sync/__manifest__.py`
- `ab_sales_sync/changelog.d/2026-08-26-sales-sync-connector.md`
