## 248a84962a0ccac2028ed220cd114a7bbf92a1a9

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Sun Aug 23 13:54:07 2026 +0300
- Subject: ab_sales_sync/ab_sales_sync now also has source_write_uid = fields.Many2one(ab_users).

User-facing changes:

- Added branch source user tracking to sales sync mirror records.

Files changed:

- `ab_sales_sync/models/ab_sales_sync_models.py`

## Current changes before commit:

User-facing changes:

- Made Sales Sync mirror identity fields optional so all `__sync` models remain schema-permissive for partial branch payloads.

Files changed:

- `ab_sales_sync/models/ab_sales_sync_models.py`
