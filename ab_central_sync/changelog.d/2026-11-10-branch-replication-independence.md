Current changes before commit:

- Document that Branch Synchronization operates independently of optional master-data replication.
- Keep central and branch workflow ownership descriptions aligned; retain existing central runtime behavior.

Files changed:

- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-10-branch-replication-independence.md

Recent relevant commit:

- Commit: 1c0a3882191adab5bd78ee783b225b9449c7574d
- Author: hossam elsheikh
- Date: 2026-11-08
- Original subject: refactor(ab_central_sync): post synchronized stock in product units
- User-facing change: synchronize stock in canonical product units and document central ownership of the inventory ledger.

Files changed:

- ab_central_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_central_sync/changelog.d/2026-11-08-branch-ledger-removal.md
- ab_central_sync/models/inventory_units.py
- ab_central_sync/workflow.md
