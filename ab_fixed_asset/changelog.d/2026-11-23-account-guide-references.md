# Fixed asset accounting catalog references — 2026-11-23

## Recent commit

- Commit: `2acef6552bec82275c919345c7fe7bca34dfde83`
- Author: Hossam Elsheikh
- Date: 2026-11-22T15:45:34+02:00
- Original commit subject: ab_fixed_asset: restrict asset access to assigned branches
- Restricted fixed asset access to users' assigned branches.

Files changed:

- `ab_fixed_asset/__manifest__.py`
- `ab_fixed_asset/changelog.d/2026-11-22-branch-isolation.md`
- `ab_fixed_asset/i18n/ar.po`
- `ab_fixed_asset/i18n/ar_001.po`
- `ab_fixed_asset/models/__init__.py`
- `ab_fixed_asset/models/ab_store.py`
- `ab_fixed_asset/security/record_rules.xml`

## Current changes before commit:

- Update four account-guide references to use the catalog owned by `ab_accounting_base`: fixed asset inventory, depreciation, accumulated depreciation, and the dynamic account lookup.
- Preserve journal document type, view, and security group references owned by `ab_accounting`.
- No user-facing strings changed; Arabic and English translations require no updates.
- No tests, database operations, or backups performed, as requested.

Files changed:

- `ab_fixed_asset/models/ab_fixed_asset_assets_inventory.py`
- `ab_fixed_asset/changelog.d/2026-11-23-account-guide-references.md`
