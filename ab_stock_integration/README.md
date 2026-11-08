# Stock integration boundary

This addon connects the existing cumulative inventory engine to opening receipts,
purchase accounting and optional native sales. It does not replace the inventory
sum calculation, purchase entry workflow or tax formulas.

It supplies store company ownership, source references and current source values
needed by those adapters. Source identity is the Odoo source model and record ID;
accounting snapshots also retain the database name. Opening receipts retain their
source document and store. Company checks apply before inventory helper reads,
and changing assigned stores invalidates cached access rules.

Native sales use each product's `ab_product_uom` category. One active reference
unit has factor 1; purchase and sale quantities convert through their canonical
unit factors. The inventory ledger accepts up to eight decimal places in the
reference unit. Unit definitions cannot change after related stock activity.

Posting locks the store and advances a private local revision record so concurrent
transactions cannot consume a stale stock snapshot. Replicated branch master
audit timestamps remain unchanged. No balance or inventory quantity is edited
directly. The existing inventory business API remains responsible for movements.

Install through the dependencies of `ab_purchase_ob`, `ab_purchase_accounting` or
`ab_sales_inventory`. Installing this addon does not switch a store to native sales.
Existing stores receive the installing company's default; verify company ownership
before enabling a multi-company pilot. Stores with stock history cannot be reassigned.

Validation and synthetic fixtures are in `scripts/stock_integration_validation/`,
outside runtime addon packages. No external database writes are required.
