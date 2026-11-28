# Fixed-asset HR branch read access

Commit: `33d0f9ed6`
Author: Hossam Elsheikh
Date: 2026-11-17
Original commit subject: `ab_fixed_asset_hr/DOCS: document access rollback`

- Documented the department-based fixed-asset access setup and rollback.

Files changed:
- `changelog.d/2026-11-15-branch-access.md`
- `changelog.d/2026-11-15-checklist-repair.md`
- `changelog.d/2026-11-17-access-rollback.md`

## Current changes before commit:

- Require an active department for the existing internal-user store rule, matching the fixed-asset branch read rules.
- Let internal users read inventory lines for their assigned stores so they can open their fixed assets. No edit permissions are granted.

Files changed:
- `security/record_rules.xml`
- `security/ir.model.access.csv`
- `changelog.d/2026-11-24-active-department-read.md`
