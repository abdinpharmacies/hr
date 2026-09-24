# Plan 05 — Port `ab_inventory` and implement stored ending balances

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer A  
**Depends on:** [Plan 08](08_ab_product_source_plan.md) and the shared quantity contract.

**Deliverables**

- Port the inventory models and fix the header relation to a real `Many2one`.
- Replace ineffective duplicate constraints and unsafe reference generation.
- Remove default branch `78`.
- Implement `ab_inventory_balance`, reservations, posting sequences, and movement `ending_balance`.
- Replace integer-only quantity handling with controlled fractional precision.
- Store product ownership explicitly so shortages do not require a fabricated physical source.
- Add structured locations for saleable, quarantine, damaged, and transit stock.
- Freeze posted quantities, conversion bases, and valuation.
- Keep pending inbound stock separate from on-hand stock.
- Restrict posting, reversal, and status transitions to authorized workflows.
- Add an integrity report and explicit balance-projection rebuild action.
- Provide batch availability and posting APIs for purchasing and POS.

**Shortages**

- Preserve authorized shortage sales with a mandatory reason.
- Use the existing 85% selling-price estimate as explicitly provisional cost.
- Reconcile later receipts against shortages oldest first by branch/product.
- Expose cost-correction events to the sales accounting adapter.
- Prevent double consumption or double counting of the deficit.

**Acceptance**

- Concurrent last-unit sales/reservations remain correct.
- Simultaneous first receipts cannot create duplicate balance rows.
- Repeated events have one effect.
- Current balances and movement ending balances match independent ledger calculations.
- Pending stock is not saleable.
- Projection repair preserves original movement quantities and values.

## Coordination and handoff

- **Module owner:** Developer A.
- **Coordinate upstream contracts and integration with:** [Plan 08](08_ab_product_source_plan.md) (Developer A).
- **Consumers of this work:** [Plan 01](01_ab_purchase_plan.md) (Developer C), [Plan 03](03_ab_purchase_accounting_plan.md) (Developer C), [Plan 04](04_ab_sales_accounting_plan.md) (Developer B), [Plan 07](07_ab_purchase_ob_plan.md) (Developer C), [Plan 09](09_ab_sales_inventory_plan.md) (Developer D).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
