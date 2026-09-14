# Abdin Sales Routing

Install `ab_sales_routing` on the branch and callcenter databases to route sales
and cashier E-Plus connections through the selected store's existing `ip1`.
Its dependencies are `ab_sales` and `ab_sales_cashier`. Installation is explicit;
there is no automatic installation, provisioning, hook, or migration.

The bridge covers sale and return connections, POS stock/customer helpers,
default-store inventory refresh, the local POS SQL status probe, and cashier
invoice reads and existing posting workflows. Default and non-default stores
both use their configured address. Missing or blank addresses fail before any
connection; no address falls back to a different store. Existing branch filters,
E-Plus product/store/transaction identifiers and business permissions remain in
place.

`ab_branch_api` is unchanged and automatically uses these inherited sales/return
helpers when the bridge is installed. Native keys, DB serial identity and API
version 1 are unchanged. The callcenter adapter retains its authenticated API
status check without a direct SQL probe or a local default-store requirement.

The legacy local POS embeds its default-store SQL target in its status method.
The bridge retains that method and redirects only its port probe using a scoped
ContextVar, reset after both successful and failed requests. The routing cannot
be selected through an RPC context value and does not persist between requests.

Known sale/return connection and access errors retain their details. Unexpected
driver exceptions produce a safe E-Plus message without a raw traceback or
credentials. No new models, ACL grants, security groups, connection fields,
menus, or scheduled jobs are introduced; inherited models keep their existing
security.

Before operational use, verify that each store's `ip1` belongs to its intended
E-Plus database. An open port alone does not establish database identity.
Installing this module does not change any stored IP or credentials. It does not
change cashier list behavior when E-Plus is unavailable: the existing list
request still needs its E-Plus query to succeed.

Validate with isolated Odoo databases and mocked E-Plus connections. Test both
stores/defaults, stock and return isolation, cashier pending-invoice reads, local
SQL status versus callcenter API status, and missing-IP rejection. No live sale,
return or other external write is part of development validation.
