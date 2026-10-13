# Schema Reference

Source: repository AGENTS.md; schema counts are a historical 2026-07-08 snapshot. Verify current columns with bounded read-only metadata queries. Do not perform broad production COUNT scans. Item/store/transaction IDs are traceability keys, not permission grants. The discovered medicine column in Phase 0 is `itm_ismedicine`; verify before substituting placeholder `itm_is_medicine` in examples.

### B-Connect / E-Plus Schema Reference

Reference source for future B-Connect to Odoo transformation work:

- GitHub repo: `https://github.com/Hossam-elsheikh/e-plus-structure`
- Primary file: `e-plus-db.md`
- Generated: `2026-07-08 15:46:57 Africa/Cairo`
- Scope: configured B-Connect/E-Plus SQL Server database `genius`

Facts from the reference guide:

- The discovered SQL Server database contains `238` user tables and `3460` columns.
- Current custom addons reference `29` E-Plus tables in SQL contexts.
- The discovery was read-only through SQL Server catalog metadata and local Odoo SQL references; broad production `COUNT(*)` scans were intentionally avoided.
- The key product and stock path is:

```text
Item_Catalog
  -> Item_Class_Store
  -> Store
```

Important table meanings:

- `dbo.Item_Catalog`: central product/item master. Key identifiers include `itm_id` and `itm_code`. Useful fields include encrypted names, units, prices, medicine flags, product groups, scientific data, usage data, origin, manufacturer/company references, and item notes.
- `dbo.Item_Class_Store`: main branch stock quantity source used by Odoo modules. It is store-scoped by `sto_id`, item-scoped by `itm_id`, class/batch-scoped by `c_id`, and quantity is represented by `itm_qty`.
- `dbo.Store`: branch/store master with `sto_id`, `sto_code`, Arabic/English names, manager/location/contact fields, store server IP fields, and replication timestamps.
- `dbo.branches`: lightweight branch/code source used by some Odoo modules, including self-inventory and order management.
- `dbo.Replication_Trans`: replication queue/transaction table for stock and transactional propagation.

Operational E-Plus / B-Connect tables for sales, stock, returns, and future Odoo-only migration:

- `r_sales_trans_h`, `r_sales_trans_d`: replicated/historical sales tables, used by Sales Per Day calculations.
- `sales_trans_h`, `sales_trans_d`: live invoice header/detail tables, used for bill status, returns, invoice lines, and returnable quantities.
- `Item_Class_Store` / `item_class_store`: stock batches by store, product, class, expiry, and price.
- `Item_Catalog` / `item_catalog`: product master, active flag, default price, and unit-of-measure conversion.
- `Store`: store and branch metadata.
- `Customer`, `Customer_Delivery`: customer lookup and reporting dimensions.
- `sales_return`, `sales_return_payment`: posted return and return-payment facts.
- `F_Transaction_Header`, `F_Cash_Store`: financial/cash impact of returns.
- `sales_deliv_info`: delivery and customer-contact snapshot.
- `employee`: employee E-Plus lookup.

For sales, inventory, returns and dashboards, read the complete
[query patterns](query-patterns.md) and their adaptation safeguards.
