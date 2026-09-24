# Plan 02 — Port `ab_accounting` and build the new UI

**Required companion:** [Master coordination plan](00_master_coordination_plan.md). Read its shared contracts, team ownership, manual-opening rules, and release gates before implementation. Those requirements apply to this plan.

**Owner:** Developer B  
**Depends on:** Shared journal contract; otherwise independent of inventory and purchasing.

**Deliverables**

- Port the existing account hierarchy, document types, journal models, and permissions.
- Remove incidental legacy dependency requirements; keep only dependencies actually required by active functionality.
- Implement the shared journal posting service.
- Replace the `< 0.99` balancing tolerance with currency-aware checks.
- Remove silent amount clamping and broad administrator/context bypasses.
- Add posting identities, period locks, source references, and separate balanced reversals.
- Preserve reviewer/freeze concepts without allowing changes to posted economic values.
- Support manual opening journals with branch, account, partner/cost-center, date, and opening-run reference.
- Provide opening balance reconciliation reports.

**Native Odoo UI**

- Journal headers with status, totals, branch, source document, and posting/reversal actions.
- Journal line entry with account, debit, credit, dimensions, and clear validation.
- Account hierarchy and account configuration.
- General ledger, trial balance, account statements, and opening-balance filters.
- Direct navigation between generated journals and their business documents.
- English source labels and Arabic translations.

**Acceptance**

- Clean installation without purchase or sales modules.
- Manual and generated journal posting use the same controls.
- Unbalanced, duplicate, unauthorized, or closed-period entries fail.
- Posted entries remain immutable; reversals are separate and traceable.
- Reports reconcile to posted lines and include manually entered openings.

## Coordination and handoff

- **Module owner:** Developer B.
- **Upstream:** shared contracts and existing foundations defined in the master plan.
- **Consumers of this work:** [Plan 03](03_ab_purchase_accounting_plan.md) (Developer C), [Plan 04](04_ab_sales_accounting_plan.md) (Developer B).
- Start independent porting and contract-based development in parallel as scheduled in the master plan; final integration acceptance requires the real upstream implementations.
- Coordinate changes to another developer’s module with its owner.
- Handoff includes implemented interface/field changes, required configuration, relevant commit references, targeted installation and business-test results, and any unresolved integration issues.
- Apply repository AGENTS.md requirements, including branch security, both Arabic translation files, module changelogs, and runtime-only production packaging.
