# Sales Upload Configuration Bridge

## Current changes before commit

User-facing changes:

- Added a small bridge module that authoritatively configures sales and return
  models as branch upload sources.
- Configured live sales and return changes on `root.sync_live` and manual
  historical upload work on `root.sync_historical`.
- Set the historical upload window to six months with a fixed cutoff of
  `2026-03-01 00:00:00`.

Files changed:

- `ab_sales_odoo_sync_upload/__init__.py`
- `ab_sales_odoo_sync_upload/__manifest__.py`
- `ab_sales_odoo_sync_upload/data/data_ab_sales_odoo_sync_upload_source.xml`
- `ab_sales_odoo_sync_upload/i18n/ar.po`
- `ab_sales_odoo_sync_upload/i18n/ar_001.po`
- `ab_sales_odoo_sync_upload/changelog.d/2026-09-06-sales-upload-configuration.md`
