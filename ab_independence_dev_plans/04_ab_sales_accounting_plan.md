# Plan 04 — Build `ab_sales_accounting`

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer B  
**Depends on:** Plans 02 and 09; allocation/valuation contract from [Plan 05](05_ab_inventory_plan.md).

**Dependencies:** `ab_sales_inventory`, `ab_sales_cashier`, and `ab_accounting`.

**Deliverables**

- Generate sale, physical return, payment, and refund journals.
- Final sale submission posts revenue/settlement and stock-cost effects.
- Cashier collection clears the settlement balance into the configured cash/payment account.
- Returns reverse the relevant sale and original issue valuation.
- Refunds reverse the relevant payment effect.
- Handle approved cashier differences using configured accounts.
- Generate linked cost corrections when provisional shortage costs become actual.
- Add journal links to sales, return, and payment records.
- Use existing customer/contract payer allocations so combined receivables equal the sale total.

**Boundaries**

- No new sales-tax calculation or assumed tax rates.
- No standalone customer debit/credit-note application in this release.
- No opening journal generation.
- No stock allocation inside this adapter.

**Acceptance**

- Sale, payment, return, and refund create distinct, nonduplicated events.
- Repeated cashier requests cannot collect or journal twice.
- Returns use original cost and remaining returnable quantity.
- An incomplete accounting configuration blocks finalization atomically.
- Revenue and cost are not reposted when the cashier collects payment.

## Coordination and handoff

- **Module owner:** Developer B.
- **Coordinate upstream contracts and integration with:** [Plan 02](02_ab_accounting_plan.md) (Developer B), [Plan 09](09_ab_sales_inventory_plan.md) (Developer D), [Plan 05](05_ab_inventory_plan.md) (Developer A).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
