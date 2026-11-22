# Fixed asset branch access

## Current changes before commit:

- Enforce active department/store assignments on fixed assets, inventory lines and asset standards. Manager and Settings roles retain cross-branch access.
- Evaluate assignments when records are accessed so a reassignment takes effect immediately. Declare the HR dependency and translate the department field into Arabic.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/ab_store.py`
- `security/record_rules.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-22-branch-isolation.md`

## 3970c027 · Hossam Elsheikh · 2026-11-18

Original commit subject: `ab_fixed_asset: fix form access`

- Omit inaccessible journal and movement details from forms for restricted users.

Files changed:

- `models/ab_fixed_asset_assets_inventory.py`
- `models/ab_fixed_asset_move_wizard.py`
- `changelog.d/2026-11-18-view-access.md`
