# Fixed asset branch access

## Current changes before commit:
- Make asset branch restrictions global so ordinary fixed-asset group grants cannot broaden branch access.
- Protect asset inventory, standards, and transfer/movement child records by their parent asset store.
- Preserve authorized manager, system-administrator and fixed-asset-accountant cross-branch access; existing ACLs continue to determine allowed operations.
- Verify denial of cross-branch header and child reads, successful same-branch reads, and manager/accountant access in an isolated database.

Files changed:
- security/record_rules.xml
- changelog.d/2026-11-15-branch-access.md

## 43af83499b32d97266353b5333a887ed62d2d5a2
Author: emadco88
Date: 2026-11-09
Subject: migrate19 INIT

- Introduce the fixed-asset HR dependency and branch read-access rules.

Files changed:
- __init__.py
- __manifest__.py
- security/ir.model.access.csv
- security/record_rules.xml
