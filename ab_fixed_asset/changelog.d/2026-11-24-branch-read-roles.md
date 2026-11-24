# Fixed-asset branch read access

Commit: `2acef6552`
Author: Hossam Elsheikh
Date: 2026-11-22
Original commit subject: `ab_fixed_asset: restrict asset access to assigned branches`

- Restricted asset headers, inventory lines, and inventory standards to assigned branches.

Files changed (relevant to this update):
- `security/record_rules.xml`

## Current changes before commit:

- Keep ordinary readers restricted to stores linked to their active departments.
- Allow Fixed Asset Accountants, Managers, Administrators, and System Administrators to read across branches.
- Preserve the existing create, write, and delete rules.

Files changed:
- `security/record_rules.xml`
- `changelog.d/2026-11-24-branch-read-roles.md`
