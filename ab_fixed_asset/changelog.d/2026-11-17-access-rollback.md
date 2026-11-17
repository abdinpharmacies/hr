# Access rollback — 2026-11-17

## Recent commit

- Commit: `fc6aae0d7f3df315c3f431e2800c1bf5ef4a41a2`
- Author: hossam elsheikh
- Date: 2026-11-12T16:35:39+02:00
- Original commit subject: ab_fixed_asset/FIX: repair asset forms and contain table scrolling

## Current changes before commit:

- Restore original ACLs, rules and financial-operation authorization; preserve movement calculations, submission/posted protections and transaction locks.
- Access behavior restored to `82ea1dc7`; prior security-repair acceptance results are historical. No user memberships or passwords changed.

Files changed:

- `ab_fixed_asset/i18n/ar_001.po`
- `ab_fixed_asset/models/ab_accounting_je.py`
- `ab_fixed_asset/models/ab_fixed_asset_assets_inventory.py`
- `ab_fixed_asset/models/ab_fixed_asset_inventory_line.py`
- `ab_fixed_asset/models/ab_fixed_asset_move_wizard.py`
- `ab_fixed_asset/views/ab_fixed_asset_assets_inventory.xml`
- `ab_fixed_asset/views/ab_fixed_asset_move_wizard.xml`
