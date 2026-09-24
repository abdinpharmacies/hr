# Plan 08 — Port `ab_product_source` for every inventory origin

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer A  
**Depends on:** [Plan 06](06_ab_taxes_plan.md) and existing product foundations.

**Deliverables**

- Support purchase receipts, openings, other receipts, transfer-in provenance, and approved adjustments.
- Retain useful product, price, cost, expiry, discount, bonus, and tax fields.
- Add stable source identity, source type, originating document, branch/database provenance, and optional legacy mappings.
- Remove fabricated default expiry dates.
- Define explicit no-expiry handling for applicable products.
- Separate physical lot identity from receipt-cost-layer identity.
- Freeze source economics used by posted movements.
- Record price-change history.
- Provide tested conversion methods for both UoM systems.
- Remove source edits that directly overwrite inventory movements.

**Acceptance**

- Every supported source origin can create a valid source without a purchase invoice.
- Equal expiry/price does not incorrectly merge distinct cost layers.
- Conversion round trips preserve allowed quantities.
- Invalid factors and forbidden fractions are rejected.
- Editing source metadata cannot rewrite historical inventory valuation.

## Coordination and handoff

- **Module owner:** Developer A.
- **Coordinate upstream contracts and integration with:** [Plan 06](06_ab_taxes_plan.md) (Developer A).
- **Consumers of this work:** [Plan 01](01_ab_purchase_plan.md) (Developer C), [Plan 05](05_ab_inventory_plan.md) (Developer A), [Plan 07](07_ab_purchase_ob_plan.md) (Developer C), [Plan 09](09_ab_sales_inventory_plan.md) (Developer D).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
