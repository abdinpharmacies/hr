# Branch API

Version **1** uses native bearer API keys and existing
`/json/2/ab_branch_api/<method>` URLs. Every request requires a positive JSON
integer `db_serial` matching server configuration and exactly one active replica.
The key must belong to the executing active internal non-administrator user.
Business ACLs and record rules remain in force; no users or mappings are created.

## Store selection and contract

All methods accept optional keyword `store_eplus_serial`. An explicit value
must be a positive JSON integer identifying exactly one active, sales-enabled
store. If omitted, the configured default sales store is used. Invalid explicit
selections and invalid defaults fail without choosing another store.

Every resolved store must belong to the replica **Allowed Sales Stores** and pass
caller read access. An empty allowed list rejects store-specific operations.
Odoo IDs may differ across installations; the selected E-Plus serial must agree.

| Method | Additional arguments | Requires a resolved store |
|---|---|---|
| `get_capabilities` | None | No |
| `get_connection_status` | None | No |
| `search_products` | `query`, `limit`, `offset` | No |
| `get_stock_lines` | `product_serials` | Yes |
| `submit_sale` | `token`, `payload`, `push_to_eplus` | Yes |
| `get_return_invoice` | `invoice`, `token`, `selections` | Yes |
| `submit_return` | `invoice`, `token`, `lines`, `notes`, `employee_ref` | Yes |
| `get_operation_status` | `token` | Yes |

Capabilities and connection checks need no SQL. With neither explicit selection
nor default, they return `store_eplus_serial: false`, `branch_store_id: false`
and `store_name: ""`. `can_post` reports business-model permissions; it does not
certify an available SQL connection or authorization for an unspecified store.

Capabilities/status, stock envelopes, sale/return results and operation status
include DB and resolved store identity. Stock rows include both identifiers;
return lines retain `sto_id` and `sth_id`. Product search retains its list result.
Callcenter always sends its connection store's E-Plus serial, and validates both
identities even for empty stock/return responses. No new connection field is used.

## Reuse branch sales workflows

The provider owns `_read_store_stock(store, product_serials)` through an inherited
`ab_sales_header` class in `models/sales_workflow.py`. It is available only inside
the authenticated private API scope. API sale-line inventory loading uses this
reader, with sales price-cache updates kept in the existing `_update_default_price()`.
The API retains its 200-product limit, product access checks and response fields.
Stock reads use committed, parameterized store/product SQL; invalid conversions
and cross-store rows fail.

Branch `ab_sales` source files are unchanged. Outside the API scope, inherited
stock and return methods delegate to `super()` and ordinary branch workflows
retain their existing behavior. Client-supplied context flags cannot activate the
private scope. The ordinary stock reader remains owned by `ab_sales`; future
changes to its calculations should also be reviewed against the API reader.

`ab_sales_header._get_store_server()` owns endpoint selection:

- Configured default store: `192.168.1.150:1433`.
- Any other selected store: its `ip1` on port `1433`.

Missing/unreachable addresses fail. API operations never use `bconnect_ip1`,
`bconnect_ip2`, or implicit fallback. Existing E-Plus credentials, database
settings, drivers and `get_connection()` methods remain in use.

A private API scope binds SQL to database, user and store, pins the endpoint at
the first SQL requirement, and isolates connections/health caches per request.
Opened connections are reused without health-check reconnection; automatic
statement replay is disabled. SQL errors propagate, and connections close and
the scope resets in `finally`. Ordinary branch connector behavior is unchanged
outside this scope.

An API-scoped `action_load_lines()` override uses the existing conversion helpers
with normal ORM permissions. Invoice/header/detail reads are parameterized and
store-filtered; quantities, prices, units and selections are preserved.
Missing/ambiguous products and stale lines reject.

The original `action_push_to_eplus()` and `action_push_to_eplus_return()` methods
still own posting. Return posting reloads through the scoped loader. A small
API-only return connection adapter adds the selected store parameter to the two
legacy inline invoice total/date reads. It does not change external write SQL,
commit, rollback, or transaction ownership. Unknown direct invoice-header SELECTs
fail closed; changes to the branch posting queries require reviewing this exact
allowlist. The invoice-status helper is also overridden only within the scope.

## Employee validation and replay

A draft return requires an explicit `employee_ref`, normally
`{"costcenter_code": "employee-code"}`. Authentication, business access and token
ownership precede employee validation; employee validation precedes external
invoice loading and reservation. Resolve exactly one branch HR employee,
including archived matches for ambiguity checks. Employee and cost center must
be active; the cost center E-Plus serial must be positive. Posting uses that
employee, never a substituted API-key owner.

Tokens belong to one user, store and operation kind. Completed identical requests
replay even after employee archival. Changed payloads reject. Processing and
uncertain operations retain their reservations and require reconciliation.
Existing recorded outcomes are returned with their authorized request identity.

## Rollout

1. For the API-only correction, keep every branch addon except `ab_branch_api`
   unchanged. Existing branch endpoint selection remains owned by its installed
   sales workflow. This release requires no routing-module uninstall.
2. Deploy branch `ab_branch_api` with the callcenter `ab_sales`
   adapter in the same maintenance window. Keep their Git changes separate.
3. Upgrade branch `ab_branch_api`; include
   `ab_branch_api_return_employee` in that same upgrade where installed.
   Upgrade callcenter `ab_sales`, restart the affected processes, and retest every
   Branch Connection before business use. Branch `ab_sales` needs no source change
   or upgrade for this rollout. Do not upgrade `base` for this change.
4. The employee extension is now an installable deprecated shell. Administrators
   may uninstall it normally after the joint upgrade. Provider validation,
   translations and operation records remain. Fresh installations need only
   `ab_branch_api`. Remove the shell directory in a later release after confirming
   it is uninstalled everywhere.

No hooks, migrations, automatic provisioning or reservation cleanup are shipped.
Validation uses isolated databases and mocked external operations. No production
deployment or live E-Plus writes are included in implementation verification.


## API-only call-center correction (19.0.5.0.0)

Only `ab_branch_api` changes on the branch. No SQL connector, branch sales source,
external database schema, hook, or scheduled job is changed. All SQL below runs
inside the authenticated branch request scope. Call-center access is HTTPS JSON-2.

Additional methods (all require `db_serial` and a resolved authorized store):

| Method | Additional arguments | Result |
|---|---|---|
| `get_product_balances` | `product_serials` (up to 200) | `data` with explicit zero balances, default prices, and `fetched_at` |
| `lookup_customer` | `phone` | Customer payload with external serial; no branch ORM customer ID |
| `create_customer` | `token`, `phone`, `name`, `address` | Idempotent branch customer workflow result |
| `get_inventory_snapshot` | `token=False`, `offset=0` | Fixed, committed inventory result, 200 rows per page |
| `get_sales_day` | `sale_date`, `token=False`, `offset=0` | Fixed result for one completed day, 200 rows per page |
| `get_invoice_statuses` | `invoices` (up to 200) | Current branch-filtered invoice statuses |
| `search_bills` | `filters={}`, `token=False`, `offset=0` | 20 branch Odoo sales/returns per page |
| `get_bill_details` | `reference` | `bill` with header/lines and permitted actions |
| `update_bill_notes` | `reference`, `notes` | Authorized update and refreshed `bill` |
| `render_bill_print` | `reference`, `print_format='a4'` | HTML only; does not dispatch to a branch printer |

Every result retains database/store identity. Bill references contain
`db_serial`, `store_eplus_serial`, `record_type` (`sale`/`return`), and `record_id`.
The last identifier is opaque and valid only inside that database/store. Access
and record rules are rechecked on every detail, notes, and print request.

Bill filters: `product_query`, `product_serials`, `customer_query`, `date_start`,
`date_end`, `eplus_serial`, `document_type`, and `status`. Default statuses are
pending/saved; drafts are explicitly selectable. E-Plus-only invoices are not
included. Customer matching on returns stays within the selected branch.

Snapshots are user/store/kind scoped and expire after one hour. The existing
Odoo transient cleanup removes old storage; there is no new cron. Continue with
the returned token and `next_offset`; `false` ends the snapshot. Clients must
collect and validate all rows before replacing a cache. Missing/invalid unit
conversion rejects inventory retrieval rather than fabricating quantities.

`create_customer` uses the existing operation reservation/hash/outcome mechanism.
A processing/uncertain outcome requires reconciliation. Completed requests replay
only with the same payload. Credentials and customer data are not included in
call-center failure logs.

Deploy this provider before the matching call-center client and retest Branch
Connections. The client checks advertised methods and rejects older providers.
Runtime and HTTP validation use isolated databases; external write workflows are
mocked. No production deployment is performed by those tests.
