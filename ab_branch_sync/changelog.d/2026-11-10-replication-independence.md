Current changes before commit:

- Install and load Branch Synchronization without Odoo Replication or its connector.
- Remove the unused replication override; preserve stock snapshots, reservations, outgoing operations and existing configuration.
- Document independent master-data replication and Branch Synchronization ownership.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/replication.py (removed)
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-10-replication-independence.md

Recent relevant commit:

- Commit: 41f1427058e7060e2faac22ca97632bf835ea4d6
- Author: Hossam Elsheikh
- Date: 2026-11-09
- Original subject: ab_branch_sync/before delivering an operation, it checks whether that operation’s store belongs to the branch’s currently configured replica. If it does not, delivery stops and the historical journal entry remains intact.
- User-facing change: retain historical outgoing operations without delivering them under a different branch identity.

Files changed:

- ab_branch_sync/changelog.d/2026-11-08-replica-switch-recovery.md
- ab_branch_sync/models/operation.py
- ab_branch_sync/workflow.md
