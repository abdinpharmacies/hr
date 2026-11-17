Current changes before commit:

- Remove the direct replication dependency and the inherited replication extension so Central Synchronization installs and runs without the replication engine or its connection module.
- Keep the Central journal, inventory transport, access rules and replica status fields in their original modules; no schema/data migration or uninstall is required.
- Document independent installation and replication-owned exclusions; increase the module version to 19.0.5.1.1.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/__manifest__.py
- ab_central_sync/models/__init__.py
- ab_central_sync/models/replication.py (removed)
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-17-replication-decoupling.md

Verification:

- Full manifest dependency traversal found no direct or indirect dependency on ab_odoo_replication or ab_odoo_connect.
- Fresh Central-only installation passed without either replication module installed.
- Eight standalone runtime checks passed, covering module/dependency state, store-scope intersection, unauthorized access, Inventory Writer enforcement, stock snapshots, journal immutability and the v3 controller.
- A targeted upgrade of both modules on a restored Central19 database passed; both remained installed and Odoo dependency metadata showed no mutual uninstall cascade. Eleven coexistence checks passed.
- Compared 270 addon tables containing 8,453,942 rows before and after the restored-database upgrade. All business records and Central parameters were preserved; only write_date changed on two existing replication rules, whose configuration remained identical.
- No user-facing source labels or messages changed; both Arabic catalogs remain unchanged. Python syntax and diff whitespace checks passed.
- Verification scripts, logs, dependency traversal and data fingerprints are retained in /tmp/central_replication_decouple. The original database and running services were not modified.

Recent relevant commit:

- Commit: ff8b0da3729e30690addf06a3b1c2c3ada2af19f
- Author: hager yasser
- Date: 2026-11-10
- Original subject: docs(ab_central_sync): document inventory workflow
- User-facing change: document inventory ownership, setup, recovery and synchronization prerequisites.

Files changed:

- ab_central_sync/changelog.d/2026-11-10-branch-replication-independence.md
- ab_central_sync/changelog.d/2026-11-10-inventory-workflow-and-uom-proposal.md
- ab_central_sync/workflow.md
