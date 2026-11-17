# Checklist repairs — 2026-11-15

## Recent commit

- Commit: `43af83499b32d97266353b5333a887ed62d2d5a2`
- Author: emadco88
- Date: 2026-11-09 15:41:15 +0200
- Original commit subject: migrate19 INIT

Established the module baseline before the current checklist repairs.

## Current changes before commit:

- Retain the existing global branch restrictions for assets and children.
- Reassign broad internal-user ACLs to the explicit Asset User group using the same XML IDs, so unrelated users lose asset reads on upgrade.

Files changed:

- `ab_fixed_asset_hr/security/ir.model.access.csv`
- `ab_fixed_asset_hr/security/record_rules.xml`
