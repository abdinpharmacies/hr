# Sales Upload Configuration Bridge

## Current changes before commit:

- Removed `ab_transfer_receive_header` and `ab_transfer_receive_line` from the
  authoritative XML sources to exclude recurring receive-refresh uploads.
- Validated XML and confirmed all 18 remaining source specifications are unchanged.
- No user-facing strings changed. No database upgrade was run for this edit.

Files changed:

- `ab_sales_odoo_sync_upload/data/data_ab_sales_odoo_sync_upload_source.xml`
- `ab_sales_odoo_sync_upload/changelog.d/2026-09-06-sales-upload-configuration.md`

## c8a394c5c60b5984b7b705151d691eb22bd2576e

Author: Hossam Elsheikh
Date: 2026-09-06 17:02:53 +0300
Original commit subject: ab_sales_odoo_sync_upload/Added high value passive models  as active authoritative sources

User-facing changes:

- Expanded authoritative upload configuration from four to 20 high-value passive
  sources: sales leads, prescriptions, transfers and requests/receipts, smart
  transfer planning, employee shifts/POS sessions/operation logs, and printers.
- Added `ab_product_barcode_temp` as a high-value passive source; its owning
  module `ab_product` is already required by `ab_sales`.
- Preserved the live/historical channels and six-month historical cutoff.
- Added manifest dependencies for the modules that define the new sources.
- Excluded operation-log heartbeats from live/prepared captures and historical
  selection; other operation logs remain eligible.
- Left smart requested-product rows independent because they can belong to a
  wizard or a transfer header.
- Omitted `ab_odoo_sync_branch_registry` and `ab_odoo_sync_upload_field_override`:
  neither model is defined in this checkout, so configuring them would fail.

Validation:

- Passed Python/XML parsing, exact classification coverage for all 19 available
  models, and isolated heartbeat upsert/archive and historical-domain checks.
- Validated 20 unique sources after adding temporary product barcodes, including
  their channel/cutoff settings and existing dependency coverage.
- Corrected invalid module translation references and merged inherited model
  labels from the Odoo-exported POT into both Arabic catalogs; both passed
  `msgfmt --check-format`.
- After restoring the missing dependency, the pending bridge upgrade completed
  on `abdin_pos`; verified all 20 sources are active.
- Targeted translation upgrade log: `/tmp/codex_sales_translation_upgrade.log`.

Files changed:

- `ab_sales_odoo_sync_upload/__init__.py`
- `ab_sales_odoo_sync_upload/__manifest__.py`
- `ab_sales_odoo_sync_upload/data/data_ab_sales_odoo_sync_upload_source.xml`
- `ab_sales_odoo_sync_upload/i18n/ar.po`
- `ab_sales_odoo_sync_upload/i18n/ar_001.po`
- `ab_sales_odoo_sync_upload/models/__init__.py`
- `ab_sales_odoo_sync_upload/models/upload_filters.py`
- `ab_sales_odoo_sync_upload/changelog.d/2026-09-06-sales-upload-configuration.md`

## ed2de30c2978ade87c9b320b12baf542dd6202ef

Author: Hossam Elsheikh
Date: 2026-09-06 10:19:48 +0300
Original commit subject: ab_sales_odoo_sync_upload/a new bridge module to set authorative upload resources data

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
