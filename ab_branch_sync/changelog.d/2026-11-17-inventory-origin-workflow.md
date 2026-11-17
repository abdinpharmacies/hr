Current changes before commit:

- Align the workflow with central's new movement attribution: authenticated replay records the originating replica serial; direct central posting uses its own serial.
- Document that removing the Inventory Stores user-form section is UI-only and does not alter permission logic or stored assignments.

Files changed:

- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-17-inventory-origin-workflow.md

Recent relevant commit:

Commit: ae6507c6df9cd3c820893f3e6f53910148a5fe0b
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-11-17T09:27:46+02:00
Original subject: ab_branch_sync/simplify central-branch connection

- Previous module change: ab_branch_sync/simplify central-branch connection.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/__manifest__.py
- ab_branch_sync/changelog.d/2026-11-16-central-sales-scope-workflow.md
- ab_branch_sync/changelog.d/2026-11-16-connection-configuration.md
- ab_branch_sync/changelog.d/2026-11-16-pos-connection-preparation.md
- ab_branch_sync/changelog.d/2026-11-16-settings-upgrade-repair.md
- ab_branch_sync/changelog.d/2026-11-16-shared-branch-inventory-access.md
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/access.py
- ab_branch_sync/models/cache.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/security/ir.model.access.csv
- ab_branch_sync/security/record_rules.xml
- ab_branch_sync/static/src/pos/central_status.js
- ab_branch_sync/static/src/pos/central_status.xml
- ab_branch_sync/workflow.md
