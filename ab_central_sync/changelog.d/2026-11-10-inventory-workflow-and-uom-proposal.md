# Inventory workflow and UoM transition documentation

Current changes before commit:

- Expand the inventory centralization workflow for operations and engineering,
  preserving the existing branch-replication independence guidance.
- Document central stock entry, branch reservations, API-key scope, event states,
  snapshot acknowledgment, cashier ownership, recovery and acceptance scenarios.
- Clarify reference-basis batch quantities versus default-sales-unit product
  balances, and label historical pilot normalization as development history.
- Add a separate proposed approach to complete legacy-unit retirement and adopt
  validated shared `convert_qty` arithmetic without changing historical stock,
  monetary agreements or immutable synchronization payloads.
- Identify the separate branch workflow alignment needed; do not modify branch
  source, production data or runtime conversion behavior in this change.

Files changed:

- ab_central_sync/workflow.md
- ab_central_sync/uom_conversion_transition.md
- ab_central_sync/changelog.d/2026-11-10-inventory-workflow-and-uom-proposal.md

## Recent relevant commit

Commit: 1c0a3882191adab5bd78ee783b225b9449c7574d

Author: hossam elsheikh <hossam.m.elsheikh@gmail.com>

Date: 2026-11-08T11:20:03+02:00

Original commit subject: refactor(ab_central_sync): post synchronized stock in product units

- Post synchronized allocations in product reference units and normalize source
  price/cost through each source's unit factor.
- Document central inventory ownership and fractional reference-unit stock.

Files changed:

- ab_central_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_central_sync/changelog.d/2026-11-08-branch-ledger-removal.md
- ab_central_sync/models/inventory_units.py
- ab_central_sync/workflow.md
