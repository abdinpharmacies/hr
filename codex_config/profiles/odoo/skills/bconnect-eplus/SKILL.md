---
name: bconnect-eplus
description: Implement or review B-Connect/E-Plus reads, item/store mapping, stock/sales SQL and queue-based migration into Odoo.
---

E-Plus remains the legacy product/branch-stock source during transition. External
DBs are read-only unless a specific write flow is explicitly authorized. Never
bypass Odoo inventory, pricing or authorization logic.

1. Reuse current connectors (`ab_eplus_connect` and actual callers). Read
   [schema and identifiers](references/schema.md); verify deployed columns and
   decryption before using encrypted/plain names.
2. Bind every stock/sales/transfer/self-inventory read to authorized branches.
   Join headers/lines by transaction AND store where required. Test branch leakage
   and equal transaction IDs in different stores.
3. Read only needed [query patterns](references/query-patterns.md). Preserved
   examples are not executable production defaults. Parameterize values and use
   the connector's IN-placeholder helper. Validate conversion factors, decimal
   arithmetic, zero/null divisors, return quantities and source units.
4. Document consistency: `NOLOCK` only when stale/dirty reads are acceptable,
   never an automatic choice for stock-critical decisions.
5. Follow [synchronization](references/synchronization.md): queue -> validation ->
   Odoo business logic -> records, with idempotency, bounded retries and audit.
   Authorized writes require branch-scoped transactions and logged E-Plus IDs;
   never casually edit `Item_Class_Store`.
6. Read [migration](references/migration.md) for transitions; retain stable IDs,
   reconcile quantities/prices per branch and preserve rollback/audit evidence.

Apply the B-Connect review rules in the main session as needed. Keep
the external schema repository as documentation, not vendored addon code.
