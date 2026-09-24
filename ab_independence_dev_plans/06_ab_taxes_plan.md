# Plan 06 — Port `ab_taxes` for purchasing

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer A  
**Depends on:** None of the purchase or accounting engines.

**Deliverables**

- Port tax definitions and configuration screens.
- Provide deterministic purchase-tax calculations shared by sources and purchase documents.
- Preserve percentage and “apply on total” concepts.
- Explicitly distinguish tax included in inventory cost from separately posted tax.
- Define configurable treatment of discounts, bonus quantities, and rounding.
- Store the approved tax calculation on finalized business documents.
- Prevent changes to tax settings from altering historical transaction values.
- Keep government tax-invoice retrieval/submission functionality outside this delivery’s active calculation path.

**Acceptance**

- Approved examples cover exempt purchases, normal taxes, compound calculations, discounts, bonus stock, and returns.
- Header totals reconcile to line/tax/rounding components.
- Purchase operations do not require an external tax-service connection.
- `ab_sales` does not acquire a new tax-calculation dependency.

**Business input:** Finance supplies approved example invoices and tax treatment; the implementation does not infer rates or policy.

## Coordination and handoff

- **Module owner:** Developer A.
- **Upstream:** shared contracts and existing foundations defined in the master plan.
- **Consumers of this work:** [Plan 01](01_ab_purchase_plan.md) (Developer C), [Plan 03](03_ab_purchase_accounting_plan.md) (Developer C), [Plan 08](08_ab_product_source_plan.md) (Developer A).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
