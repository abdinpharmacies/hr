Current changes before commit:

- Keep historical operations visible while skipping delivery for stores outside the configured branch replica.
- Document how retries behave when an experimental branch database changes replica identity.

Files changed:

- ab_branch_sync/models/operation.py
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-08-replica-switch-recovery.md

Recent relevant commit:

- Commit: 8a99a895
- Author: hossam elsheikh
- Date: 2026-11-08
- Original subject: refactor(ab_branch_sync): remove branch inventory dependency
- User-facing change: branch stock comes from central snapshots without the branch inventory ledger.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_branch_sync/changelog.d/2026-11-08-branch-inventory-removal.md
- ab_branch_sync/models/cache.py
- ab_branch_sync/workflow.md
