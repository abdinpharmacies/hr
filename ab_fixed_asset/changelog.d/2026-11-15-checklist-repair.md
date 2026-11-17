# Checklist repairs — 2026-11-15

## Recent commit

- Commit: `fc6aae0d7f3df315c3f431e2800c1bf5ef4a41a2`
- Author: hossam elsheikh
- Date: 2026-11-12 16:35:39 +0200
- Original commit subject: ab_fixed_asset/FIX: repair asset forms and contain table scrolling

Established the module baseline before the current checklist repairs.

## Current changes before commit:

- Retain prior uncommitted valuation, movement, notification, form and translation repairs.
- Give asset roles the required read-only references and journal access; keep automatic journal creation and branch updates inside validated asset workflows.
- Translate negative useful-life validation, inventory and cost-center labels in both Arabic language files.

Files changed:

- `ab_fixed_asset/i18n/ar.po`
- `ab_fixed_asset/i18n/ar_001.po`
- `ab_fixed_asset/models/ab_accounting_je.py`
- `ab_fixed_asset/models/ab_fixed_asset_assets_inventory.py`
- `ab_fixed_asset/models/ab_fixed_asset_inventory_line.py`
- `ab_fixed_asset/models/ab_fixed_asset_move_wizard.py`
- `ab_fixed_asset/security/ir.model.access.csv`
- `ab_fixed_asset/security/record_rules.xml`
- `ab_fixed_asset/views/ab_fixed_asset_assets_inventory.xml`
- `ab_fixed_asset/views/ab_fixed_asset_move_wizard.xml`
