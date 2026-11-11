# Plan 09 — Connect existing sales and cashier to native inventory

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer D  
**Depends on:** [Plan 05](05_ab_inventory_plan.md); shared source/UoM contract from [Plan 08](08_ab_product_source_plan.md).

**Deliverables**

- Implement `ab_sales_inventory` while preserving the POS window.
- Replace native-path E-Plus reads/writes for availability, source allocation, sales, returns, and cashier settlement.
- Read availability from `ab_inventory_balance`.
- Preserve the existing POS inventory payload shape through an adapter.
- Select matching-price sources first, then the existing fallback price/expiry ordering.
- Revalidate and persist exact allocations at posting.
- Exclude expired, quarantined, and damaged stock from normal sale.
- Implement branch-owned reservations and authorized shortage handling.
- Create native payment/refund records and cashier balances.
- Expose finalized business events consumed by `ab_sales_accounting`.
- Preserve current promotions, contracts, employee permissions, price badges, and UoM behavior.
- Isolate legacy backend behavior so a native operation cannot also execute E-Plus posting.

**Acceptance**

- A full sale/payment/return/refund cycle works with SQL Server unavailable.
- POS searches and batch reads do not aggregate the full movement ledger.
- Double-clicks and request retries cannot duplicate stock or payments.
- Cashier settlement does not consume stock a second time.
- The existing POS extensions remain functional.
- Historical-return requests without imported original transactions follow an explicit manual process rather than guessing allocations.

## Coordination and handoff

- **Module owner:** Developer D.
- **Coordinate upstream contracts and integration with:** [Plan 05](05_ab_inventory_plan.md) (Developer A), [Plan 08](08_ab_product_source_plan.md) (Developer A).
- **Consumers of this work:** [Plan 04](04_ab_sales_accounting_plan.md) (Developer B).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
