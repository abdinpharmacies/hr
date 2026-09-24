# Plan 01 — Port and decouple `ab_purchase`

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer C  
**Depends on:** Shared source, tax, and inventory contracts; completed implementations for final integration.

**Deliverables**

- Port Python, security, XML views, actions, and required dependencies to Odoo 19.
- Remove the direct dependency on `ab_accounting`.
- Extract journal generation, journal delegation, accounting fields/views, supplier claims, financial reports, and accounting-specific security into `ab_purchase_accounting`.
- Preserve purchasing document model names and existing business identifiers.
- Retain invoice capture, validation, receipt review, source creation, paid/bonus quantities, and supplier returns/notices.
- Preserve the existing purchase status keys, with explicit authorized transitions.
- Pending receipt documents do not increase saleable stock. Final branch acceptance posts stock once.
- Create immutable inventory posting events through `ab_inventory_process`.
- Replace placeholder returnable quantities with accepted receipts minus previous returns.
- Separate physical supplier returns from financial-only price corrections.
- Remove hardcoded branch fallbacks and source-to-stock write-through behavior.
- Expose business posting extension methods for the optional accounting adapter.

**Acceptance**

- Clean install and complete purchase/return workflow without `ab_accounting`.
- Paid and bonus quantities produce correct source layers and stock.
- Repeated approval does not duplicate inventory.
- Returns cannot exceed eligible quantities.
- Branch users cannot access another branch’s documents or lines.

**Deferred:** separate purchase orders, partial receipts, and three-way matching.

## Coordination and handoff

- **Module owner:** Developer C.
- **Coordinate upstream contracts and integration with:** [Plan 06](06_ab_taxes_plan.md) (Developer A), [Plan 08](08_ab_product_source_plan.md) (Developer A), [Plan 05](05_ab_inventory_plan.md) (Developer A).
- **Consumers of this work:** [Plan 03](03_ab_purchase_accounting_plan.md) (Developer C).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
