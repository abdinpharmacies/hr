# Native sales inventory

This optional Odoo 19 addon connects the existing sales/POS/cashier screens to
`ab_inventory`. Each store has an explicit backend configuration; the default
continues to use the existing E-Plus backend. Native stores operate without a
SQL Server connection. Historical legacy invoices retain their original backend.

Administrators configure the backend before creating native documents. Operators
need the Native Sales role, assigned inventory stores and an authorized employee
session. Cashier operations additionally require cashier permissions. Backend
changes are refused while documents remain open or would strand posted native
sales and their returns.

Submitting a native sale reserves and consumes exact source allocations in one
transaction. Repeated checkout cannot consume stock twice. Settlement records
one payment, makes the invoice available for returns and leaves stock unchanged.
Returns restore original allocations; shortages retain their authorized deficit
and later actual-cost correction history. Missing historical originals require
review rather than reconstructed allocations.

Posted sales retain totals, source quantities, unit conversion and service
classification. Local contract and promotion hooks calculate customer payments
and refunds. Employee return permissions and required manager authorization are
enforced on the server. Raw payment/refund/cash-balance writes are forbidden.
Cash counts record expected, counted and difference amounts without clearing
settlement balances; cash remittance is a later independence workflow.

Configure the product's native unit category, default selling unit, smallest
stock unit and quantity increment before the first sale. Units in a category
used by posted native sales cannot change their factors or categories.

Both Arabic catalogs accompany English source strings. Tests and synthetic
fixtures are kept under repository `scripts/`, outside runtime addon packages.
See `ab_independence_dev_plans/13_phase_1_6_execution.md` for measured validation
and remaining business/rollout gates. Accounting adapters are deferred.
