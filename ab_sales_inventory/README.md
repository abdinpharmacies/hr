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

Approving a native sale freezes its bill totals, allocates matching-price sources,
deducts available stock and records any authorized shortage in one transaction.
The invoice then remains pending for cashier collection. Cashier settlement uses
the frozen approval snapshot and never deducts stock again. Repeated approval and
settlement requests are idempotent, while reuse of a request token with changed
content is rejected. Sending an approved return to the cashier restores the
original source allocations once; refund collection creates no stock movement.
Missing historical approvals require review rather than reconstructed allocations.

Posted sales retain totals, source quantities, unit conversion and service
classification. Local contract and promotion hooks calculate customer payments
and refunds. Employee return permissions and required manager authorization are
enforced on the server. Raw allocation, shortage, reversal, payment, refund and
cash-balance writes are forbidden. System administrators may cancel pending
native invoices, restoring only their deducted source quantities without creating
payment or refund effects. Cash counts are supplied by the optional cashier addon.

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

The sold-without-stock report is read-only, independently permissioned and scoped
by the user's authorized branches. It records the sold, deducted and shortage
quantities with the approval reason. No scheduled or automatic shortage
reconciliation is performed.
