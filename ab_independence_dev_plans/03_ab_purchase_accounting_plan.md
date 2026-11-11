# Plan 03 — Build `ab_purchase_accounting`

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer C  
**Depends on:** Plans 01, 02, 06, and 07; stock valuation contract from [Plan 05](05_ab_inventory_plan.md).

**Dependencies:** `ab_purchase`, `ab_purchase_ob`, `ab_accounting`, with direct dependencies declared for any additional models used.

**Deliverables**

- Move purchasing accounting functionality out of `ab_purchase`.
- Preserve supplier claims and settlement/reporting functionality under this adapter.
- Add explicit journal relations and inherited accounting views.
- Generate journals automatically at final approval of purchases and supplier returns/notices.
- Use the approved purchase tax/value snapshot, not a fresh calculation from potentially changed source fields.
- Post physical returns using original receipt valuation.
- Financial-only notices adjust value without creating stock quantity.
- Handle later cost corrections through linked adjustment entries.
- Generate journals for approved non-purchase receipts using their configured offset accounts.
- Explicitly exclude opening-stock documents from automatic journals.

**Posting ownership**

| Event | Accounting treatment |
|---|---|
| Accepted purchase | Inventory and configured tax against supplier balance |
| Physical supplier return | Reverse the applicable supplier, tax, and inventory amounts |
| Financial-only notice | Adjust the appropriate supplier/value accounts without stock quantity |
| Non-purchase receipt | Inventory against the approved receipt-type offset account |
| Opening inventory | Manual opening accounting; no automatic duplicate |

**Acceptance**

- Installing the adapter enables future automatic journals.
- Existing finalized documents are not backfilled.
- Each supported event creates one balanced financial effect.
- Missing mappings roll back stock/document posting.
- Manual inventory opening values are not posted a second time.
- Purchase accounting screens and claims are absent when the adapter is absent.

## Coordination and handoff

- **Module owner:** Developer C.
- **Coordinate upstream contracts and integration with:** [Plan 01](01_ab_purchase_plan.md) (Developer C), [Plan 02](02_ab_accounting_plan.md) (Developer B), [Plan 06](06_ab_taxes_plan.md) (Developer A), [Plan 07](07_ab_purchase_ob_plan.md) (Developer C), [Plan 05](05_ab_inventory_plan.md) (Developer A).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
