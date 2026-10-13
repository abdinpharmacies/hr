# Synchronization and Write Boundaries

Reuse the installed connector. Idempotency keys must distinguish source, store, transaction/line and operation/version as appropriate. Validate before applying through Odoo business methods; record outcomes and external IDs, use bounded retries and quarantine failures. Never automatically retry an uncertain external write without reconciling its transaction ID.

Write-sensitive E-Plus tables:

- Sales: `sales_trans_h`, `sales_trans_d`, `sales_deliv_info`, `sales_return`, `sales_return_payment`, `sales_trans_payment`.
- Inventory: `Inventory_h`, `Inventory_d`, `Item_Class_Store`.
- Transfers: `Store_Trans`, `Store_Trans_h`, pending transfer tables.
- Finance/cash: `F_Cash_Store`, `F_Transaction_Header`, `F_Auto_Doc_h`, `F_Auto_Doc_d`.
- Replication: `Replication_Trans` and `r_*` replication/staging tables.

B-Connect development rules:

- Treat E-Plus/B-Connect as an external source of truth for legacy product and branch stock data during the transition, but do not bypass Odoo business logic when creating Odoo records.
- Never directly update `Item_Class_Store` outside explicitly approved sales, returns, inventory, transfer, or replication flows.
- For reads, use `WITH (NOLOCK)` only when stale reads are acceptable. Stock-critical workflows must explicitly decide and document their consistency requirement.
- For existing write flows, every operation must be transactional, branch-scoped, and must log the pushed E-Plus transaction identifier.
- For future broad synchronization from E-Plus into Odoo, use queue-based imports, validation, idempotency keys, and audit logs.
- Before adding a new B-Connect connection implementation, search existing modules for current E-Plus/B-Connect helpers and reuse the established connector pattern where possible.
- Do not vendor or copy the `e-plus-structure` repo into Odoo addons. Treat it as reference documentation only.
- Any migration from B-Connect to Odoo must preserve stable identifiers such as `itm_id`, `itm_code`, `sto_id`, `sto_code`, and transaction IDs for traceability.
- All stock, sales, transfer, and self-inventory reads must be branch-filtered. Multi-branch code must test that one branch cannot receive another branch's rows.
- Product names may exist in encrypted fields such as `itm_name_ar_encrypt` and `itm_name_en_encrypt`; do not assume plain name columns are populated without confirming the decryption path.

### Replication Safety Rules

Use an integration queue pattern:

```text
External DB
  -> Import Queue
  -> Validation
  -> Odoo Business Logic
  -> Final Records
```

Avoid direct writes:

```text
External DB
  -> Direct Write
  -> Production Tables
```

Queue-based imports make troubleshooting and recovery much safer.
