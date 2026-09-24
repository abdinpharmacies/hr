# Plan 07 — Port `ab_purchase_ob` for openings and other receipts

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer C  
**Depends on:** Plans 05 and 08.

**Deliverables**

- Support two explicit document purposes:
  - **Opening inventory**.
  - **Non-purchase receipt**.
- Require branch, source details, quantities, UoM, value, date, and receipt reason.
- For non-purchase receipts, configure receipt types used by the accounting adapter to select offset accounts.
- Remove unnecessary purchase/accounting coupling from the core module.
- Stage manually supplied openings, validate them, and post approved movements once.
- Preserve source provenance without requiring E-Plus identifiers for new sources.
- Link opening documents to an opening-run/cutoff reference.
- Restrict opening mode after the branch’s opening run is closed.
- Reverse posted mistakes through linked corrective documents.

**Boundaries**

- This module records receipts that are not supplier purchases.
- It does not replace transfer receipts, sales returns, or stock-count approvals.
- Operators must not record the same arrival through both this module and its owning workflow.

**Acceptance**

- Approved openings immediately appear in the correct inventory balances.
- Repeated import/approval does not duplicate stock.
- Opening stock creates no automatic journal.
- A later non-purchase receipt creates a journal only when `ab_purchase_accounting` is installed and configured.
- The module works without the accounting adapter.

## Coordination and handoff

- **Module owner:** Developer C.
- **Coordinate upstream contracts and integration with:** [Plan 05](05_ab_inventory_plan.md) (Developer A), [Plan 08](08_ab_product_source_plan.md) (Developer A).
- **Consumers of this work:** [Plan 03](03_ab_purchase_accounting_plan.md) (Developer C).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
