# Native sales inventory

This optional Odoo 19 addon connects the existing sales/POS/cashier screens to
`ab_inventory`. Each store has an explicit backend configuration; the default
continues to use the existing E-Plus backend. Native stores operate without a
SQL Server connection. Historical legacy invoices retain their original backend.

Administrators configure the backend before creating native documents. Operators
need the Native Sales role, assigned inventory stores and an authorized employee
session. Cashier operations additionally require cashier permissions. Native activation may retain historical legacy drafts, which cannot reconnect or
repost after cutover. Changing an active native backend is refused when it would
strand open or posted native sales and their returns.

Submitting a native sale freezes its bill totals and sends it to the cashier.
Draft and submitted sale lines create no stock movements or reservations.
Cashier settlement allocates available sources and calls the cumulative inventory
API in the same transaction as payment. Insufficient stock leaves the bill pending;
a later failure rolls back both stock and payment. Repeated settlement cannot
consume stock twice. Cashier refunds restore the original source allocations.
Missing historical originals require review rather than reconstructed allocations.

Posted sales retain totals, source quantities, unit conversion and service
classification. Local contract and promotion hooks calculate customer payments
and refunds. Employee return permissions and required manager authorization are
enforced on the server. Raw payment/refund/cash-balance writes are forbidden.
Cash counts record expected, counted and difference amounts without clearing
settlement balances; cash remittance is a later independence workflow.

Configure the product's sales unit category, default selling unit and legacy
smallest inventory unit. Set Sales Unit for One Stock Unit to the sales unit
equivalent to that smallest inventory unit, or use Stock Conversion Sales Unit
with its exact number of smallest stock units. Fractional selling quantities must
convert exactly to positive whole stock units. Units in a category used by
submitted native sales cannot change their factors or categories.

Both Arabic catalogs accompany English source strings. Tests and synthetic
fixtures are kept under repository `scripts/`, outside runtime addon packages.
See `ab_independence_dev_plans/13_phase_1_6_execution.md` for measured validation
and remaining business/rollout gates. Accounting adapters are deferred.

Stores 29 and 140 on `rip_bconnect` were activated locally on 2026-10-19 with
approved synthetic opening receipts of 1,000 default sales units per billed
stock product. Create new invoices for the native cycle. Remote reporting sync,
shared shift closing batches, treasury transfers and next-cashier handover are
not implemented by this cutover. Existing cashier balances remain per user.
