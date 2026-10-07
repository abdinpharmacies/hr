# Callcenter and Branch Connection Guide

API version remains **1**. All eight methods require positive JSON integer `db_serial` and accept optional
keyword `store_eplus_serial`. Callcenter always sends the selected store serial. `store_serial` is rejected. URLs remain `/json/2/ab_branch_api/<method>`.
The branch implementation lives in `custom-addons/ab_branch_api`; the callcenter
adapter lives in `worktrees/callcenter/ab_sales`.

## Provisioning

Provision existing users, business permissions, native Odoo API-key records,
replica metadata, and server configuration through your deployment system. The
addon creates no users, groups, bindings, or credentials. There is no branch
preparation wizard or dedicated API role.

Any active internal non-administrator user with the required business permissions
may connect using their own key. User IDs and logins need not match across
servers. Settings administrators, access administrators, the superuser, and
portal/public users cannot call this API.

For provisioned native `res_users_apikeys` records, the owner must be the correct
**local branch user**. Store a native PBKDF2-SHA512 key hash in `key` and the first
eight raw-key characters in `index`, with `rpc` (or unrestricted) scope and the
intended expiry. Callcenter receives the corresponding **raw key**, never the
hash. Native Odoo verification checks owner activity, scope, expiry, and the
complete hash. A prefix alone cannot authenticate. No seeding implementation is
included in either addon.

## Identity mapping

| Value | Meaning |
|---|---|
| `db_serial` | Shared branch identity, equal to the branch server configuration and its active `ab_replica_db.db_serial` |
| `store_eplus_serial` | Selected store E-Plus serial; exactly one active sales-enabled store must match on the branch and belong to the replica Allowed Sales Stores (an empty list rejects) |
| Callcenter selected store | Chooses the active Branch Connection for that sale or return; no local replica/default-store mapping is required |
| Store Odoo ID | Local identifier; may differ between servers and from DB/store serials |
| `rpc_db` / X-Odoo-Database | Exact remote PostgreSQL database name, separate from DB serial |
| Product / invoice identifiers | Existing E-Plus identifiers; their meanings do not change |

The adapter derives `store_eplus_serial` from the connection's selected store;
no new connection field is needed. Store E-Plus serials must agree across servers.
Without an explicit selection, the provider uses its default sales store.
Connection/capability checks and product search may proceed without either;
store-specific operations require a resolved store. An invalid explicit selection
or invalid default rejects without falling back. Empty allowed-store lists deny
store-specific operations. The default uses `192.168.1.150`; other stores need `ip1`.

The branch uses its resolved store's E-Plus serial in stock and transaction
queries. Live stock and invoice ownership checks read committed source data;
posting revalidates through existing business workflows. Each query is scoped
to the resolved branch store.

## Callcenter setup

1. Configure one Branch Connection for each store employees can select during
   sales and returns. Use that branch server's DB serial; no matching local
   replica record or default sales store is required in callcenter.
2. In **Sales → Configuration → Branch Connections**, enter the store, DB serial,
   HTTPS branch URL, exact remote PostgreSQL database name, and raw API key.
3. Save and run **Test Connection**. Require **Ready** and **Success**. Review the
   returned store, user, expiry, and posting capability.

API keys are stored as plaintext in the callcenter database. The GUI masks the
stored value; only Settings administrators can access it, it is not copied or
tracked in chatter, and credential exports are blocked. Errors redact the key.
No branch-connection encryption configuration is required.

Replacing or clearing a key, or changing the URL, database, store, DB serial or
activation, invalidates verification. Test again before business use. Connections
without a key cannot be used even if an older release marked them Ready.
**Test Connection** and **Check Connections** run synchronously and manually.
Results and administrator alerts remain; there are no scheduled connection checks,
queued connection checks, or credential rotation actions. Inventory, sales-history
and submitted-invoice status synchronization retain their existing API schedules.

## Manual test checklist

After loading the updated addon code, target-upgrade `ab_sales` on callcenter
and restart its Odoo process so the form and renamed status are visible. If the
branch API changes have not yet been loaded, target-upgrade the branch addons
`ab_branch_api` and restart that process too. Never upgrade `base` for
this change.

1. **Connection:** enter Branch, DB Serial, Branch Odoo URL, Branch Database,
   and the raw native API Key. The database name is the remote PostgreSQL name;
   DB Serial must match the branch server config and its active replica record.
   Save and click **Test Connection**. Expect **Ready**, a successful last test,
   the correct **Verified Branch** and integration user, and **Posting Allowed**
   for a user with full sale/return permissions. On failure, read **Last Test
   Message**. No E-Plus business operation is executed by this connection test.
2. **Branch selection:** configure a second connection if available. Neither
   connection needs a matching replica/default-store record in callcenter.
   Log in as a callcenter employee and select each branch in turn.
3. **Stock:** select a known product and check that displayed availability and
   prices correspond to the selected branch.
4. **Sale submission:** submit a small sale and verify the branch first creates
   its Odoo invoice as `prepending`, automatically runs the normal branch sale
   submission, and returns `pending` with a positive E-Plus serial. Repeat for
   the other branch and confirm the first branch does not receive that sale.
5. **Return preview:** select the branch and enter an existing saved invoice
   from it. Load the return lines and verify products, quantities, costs and
   totals. Loading creates/updates a return draft without posting a return.
6. **Full posting:** use a test branch and test E-Plus database. Verify the
   resulting sale is visible to cashier, complete it, and confirm callcenter
   synchronizes `pending` to `saved`. Submit a return there and verify its
   return/financial identifiers.
7. **Wrong identity:** change a connection's DB Serial to a different positive
   value and test it. Expect rejection. Restore the correct value and test again
   to recover **Ready**. Saving an identity or credential change requires fresh
   verification before business use.

The form shows connection essentials and the last test result. **Advanced
Settings** contains activation, the administrator responsible for connection alerts,
and request timeout. The duplicate connection name/code, raw remote store ID,
and extra success timestamp are not shown. Credential expiry appears only when
one exists. **Verification Required** replaces the old **Enrollment Required**
label; no enrollment wizard is needed.

## Request and response contract

```http
POST https://branch.example.com/json/2/ab_branch_api/get_connection_status
Authorization: bearer <raw native Odoo API key>
X-Odoo-Database: <remote PostgreSQL database name>
Content-Type: application/json

{"db_serial": 102, "store_eplus_serial": 7}
```

Every method validates the bearer credential again and requires its owner to
match the executing user. Session authentication alone is insufficient. Invalid,
revoked, expired, wrong-scope, or inactive-owner credentials fail. Inherited
`decrypt_password()` is private to RPC on `ab_branch_api`; internal connector
calls continue through the inherited implementation.

| Method | Additional arguments |
|---|---|
| `get_connection_status` | None |
| `get_capabilities` | None |
| `search_products` | `query`, `limit`, `offset` |
| `get_stock_lines` | `product_serials` |
| `submit_sale` | `token`, `payload` |
| `get_return_invoice` | `invoice`, `token`, `selections` |
| `submit_return` | `invoice`, `token`, `lines`, `notes`, `employee_ref` |
| `get_operation_status` | `token` |

Callcenter sends both identity arguments in addition to those listed above.
The callcenter has no E-Plus submission setting and sends no transport choice.
The branch first creates the sale as PrePending, then automatically runs its
normal sale submission logic. A normal successful response is Pending with a
positive E-Plus serial, making the invoice visible to the branch cashier.
Capabilities return `version`, `db_serial`, `store_eplus_serial`, `branch_store_id`, `store_name`,
`can_post`, and `methods`. Connection status adds `credential_id`, `expires_at`,
`user_id`, and `login`. No raw credential or hash is returned; no-expiry keys
return `expires_at: false`.

Read operations require sales/product read permissions. Sale submission requires
sale header/line read, create, and write permissions. Return preview and posting
require return header/line read, create, and write permissions as previews can
create or update drafts, plus sales/product read permissions. `can_post` reports
whether both sale and return permissions are present; individual operations
still enforce their own permissions and record rules. Costs are returned to
eligible callers without a separate API cost flag.

Stock envelopes and rows, sale/return results and operation status include both
`db_serial` and `store_eplus_serial`. Callcenter validates both, including empty
stock/return responses. Return lines also retain invoice/store checks through
`sth_id` and `sto_id`. Product search retains its list response.

## Operations and rollout

Tokens belong to one user, store, and operation kind. Reusing a token from another
user/store is rejected; another user's status cannot be read. Completed unchanged
requests replay their result. Changed payloads fail; processing or uncertain
bill outcomes reconcile automatically inside the branch API on retry.
**Branch API → Operations** retains the audit journal for administrators.
Do not switch users or tokens to bypass uncertain outcomes.

There is no distributed transaction between SQL Server and PostgreSQL. Existing
branch workflows reserve operations before posting and retain transaction IDs
for reconciliation. Validation must mock E-Plus operations.

Deploy both addon changes together to clean installations. No compatibility
layer, lifecycle hook, migration, or automatic provisioning is shipped. Use only
targeted upgrades (`ab_branch_api` on branch and `ab_sales` on callcenter),
then provision/test connections before business use. This source change does not
deploy or execute live E-Plus writes.


## POS connection diagnostics

The callcenter POS checks the selected Branch Connection using the authenticated
`get_connection_status` API and verifies its DB serial. **Branch API connected**
means that Odoo and the credential are working; it does not test E-Plus. An API
failure shows **Branch API unavailable**, with the business error in a notification
and the badge tooltip. Changing the selected branch discards older status responses.

### Reused sales workflows and API SQL safety

The provider reuses branch `ab_sales_header._get_store_server()`:
configured default store → `192.168.1.150:1433`; another selected store → its
`ip1:1433`. Missing/unreachable endpoints fail. There is no `bconnect_ip1`,
`bconnect_ip2` or implicit API fallback. Existing credentials and drivers remain.

The provider owns its read-only `_read_store_stock()` helper and scoped inventory
and return-loading overrides in `ab_branch_api`. Sales price-cache updates stay
outside the reader. Reads are parameterized and store-filtered, use committed
data, and retain quantities, costs, prices and expiry. Return loading reuses branch
conversion helpers with normal ORM permissions and retained units and selections.
Existing sale/return business methods still execute posting. Branch `ab_sales`
source is unchanged; ordinary calls delegate to the original implementations.
The API return adapter filters the legacy inline invoice total/date reads without
copying external write logic. Branch query changes require an adapter review.

API SQL connections are isolated per database/user/store request. The endpoint is
pinned; opened connections are reused without reconnecting or replaying statements.
The scope resets and its connections close on exit. Callcenter never automatically
repeats an unconfirmed external post. The branch reconciles uncertain bill results
before allowing a retry with the same request.

Capabilities and Test Connection are independent of SQL availability. Without a
selected/default store, the API can return false store IDs and an empty store name.
Callcenter connection testing always supplies a store and requires a matching
resolved identity before marking the connection Ready. `can_post` reports model
permissions, not SQL health or permission to post to an unspecified store.

Before rollout, administrators must manually uninstall `ab_sales_routing` where
installed and verify ordinary branch routing. No automatic uninstall is included.
Deploy branch `ab_branch_api` with this callcenter adapter (branch `ab_sales`
requires no change or upgrade), then restart
and retest connections. Validate using isolated databases and mocked external
operations; do not perform live E-Plus writes during implementation validation.

## Return employee identity

POS returns send the employee from the active employee session. The session
must belong to the current Odoo user and permit the return screen and selected
store. A session employee takes precedence over any form selection.

An Administrator submitting from the standard Sales Return form must choose
**Return Employee**. Other users must use an active employee POS session.
The selected employee and cost center must be active, with a cost center code
that identifies the same employee on the branch. The callcenter does not need
the branch employee's local Odoo ID or E-Plus serial.

Upgrade `ab_branch_api` on the branch and this callcenter `ab_sales` adapter.
The provider requires exactly one active branch HR employee
with an active cost center and a positive cost center E-Plus serial. It checks
that mapping before an invoice reservation or external invoice query. The
callcenter Administrator is separate from the native API-key owner, which must
remain an eligible internal non-administrator branch user.

To test, submit a new draft without an employee and verify local rejection.
Select an employee whose branch mapping is missing and verify a branch mapping
error with no reservation. Correct the branch mapping through the normal
provisioning process and retry the draft. For actual posting use a dedicated
test E-Plus environment. Repeat through POS and confirm the logged-in employee
is used. Completed requests retain their normal replay protection; do not
change the employee or other payload data when retrying a submitted request.

Uncertain bill operations are reconciled by the branch API. Reservations are
released only after confirmed completion; conflicting evidence stays blocked. Completed identical requests replay even if
the employee is subsequently archived.

### Retire the old employee extension

If `ab_branch_api_return_employee` is installed, deploy its deprecated shell in
the same rollout and upgrade `ab_branch_api,ab_branch_api_return_employee`
together. Its validation and translations now belong to `ab_branch_api`.
Administrators may then uninstall the shell normally; existing API operation
records and validation remain. Fresh installations need only `ab_branch_api`.
Remove the obsolete directory in a later release after confirming it is
uninstalled everywhere. No hooks, automatic uninstall or migrations are included.

Deploy provider and callcenter contract changes together and retest connections.
Omitted `store_eplus_serial` uses the provider default when valid. Explicit invalid
selections never fall back. Callcenter always sends its selected store; there is
no automatic provisioning.


## API-only callcenter (19.0.3.5.0)

This checkout always uses the branch API. It contains no SQL connector inheritance,
external SQL posting or fallback, connection probes, or transport-role selection.
The branch provider retains its E-Plus connection and owns automatic sale posting.
Response identifiers retain their branch API meaning; this release does not make
the branch backend independent of E-Plus.

### Deployment

1. Before upgrading, manually disable the former connection health/rotation
   scheduled actions and cancel unfinished jobs targeting the removed connection
   management method. Pause the callcenter service while performing the upgrade.
2. Target-upgrade branch **ab_branch_api**, then callcenter **ab_sales**; never
   upgrade base. No credential conversion, migration, hooks, historical import
   or automatic cleanup is shipped.
3. Remove the former server-role environment setting from the callcenter service.
   Retain queue-runner configuration and the encryption configuration key wherever
   other installed addons still need them. Do not uninstall shared dependencies
   merely because ab_sales no longer requires them.
4. Restart callcenter. Enter each existing API key manually, save, and run
   **Test Connection**. Require Ready and Success and inspect identity, expiry and
   posting capability before using the branch.

Active Branch Connections define available remote stores. Existing configured
local Allowed Sales Stores, when present, further restrict them; normal store
record rules still apply. A local replica/default store is not mandatory.

Stock, price cache, product details, customer lookup/creation, sales and returns
use the authenticated branch API. The all-store balance dialog queries each
permitted connection. Read failures retain cached values and mark them stale;
missing responses never become zero stock. Price-cache changes log old/new price,
store/product, user and refresh time. Customer cache records are mapped by stable
E-Plus serial and created through ORM when absent; no SQL lookup is performed.

Existing inventory, completed-day sales-history and invoice-status jobs use API
snapshots/batches. No new jobs are added. Inventory snapshots are validated before
applying or clearing absent balances. Sales-day replacement waits for every
required branch and affects only those authorized stores. Other branches and
failed-day history remain unchanged.

### Local bills (19.0.3.3.0)

The callcenter stores each sales header and its lines before requesting branch
submission. Local return headers and lines are retained as well. Browsing,
details and printing use these records, even while a branch is unavailable.
No historical branch bills are imported or reconstructed from RPC logs.

- **Bills** opens the native sales list/form. **Sales Return** opens the separate
  return list/form. **Bill Wizard** keeps its combined sales/returns layout.
- All three states are visible: PrePending, Pending and Saved. Local browsing
  and status synchronization do not depend on `is_callcenter_order`; that field
  remains protected metadata for existing submission workflows.
- A failed sale remains a local PrePending draft. Open it in Bills and use
  **Retry Submission**. The original request, branch database identity, posting
  payload and request token are retained. Submitted request contents are locked.
  The branch API automatically checks the original transaction before retrying:
  it returns an already-posted bill or safely reuses the same draft after a
  proven rollback. There is no automatic submission queue.
- A successful branch response supplies the local bill's status, branch bill ID
  and `eplus_serial`. Returns retain their submission response status and
  `sales_return_id`.
- The **Sales: Synchronize Branch Sale Statuses** cron runs every five minutes.
  It requests locally submitted PrePending and Pending sales by their original
  tokens, using `get_sale_statuses` in batches of up to 200. Matching includes
  branch database/store identity and branch header ID. Only validated lifecycle
  fields are updated; bill content is retained.
- Explicit wizard searches and changes to the sales list's search domain run
  the same status refresh before applying status filters. Initial browsing,
  pagination, details and printing do not require branch connections. Missing
  or malformed results and unavailable branches retain the previous status;
  searches still show local records with a warning.
- Saved sales and returns are not polled. Missing tokens, malformed results,
  invalid serials and lifecycle regressions leave the local record unchanged.
- Branch-assigned users are limited to their department/employee branches.
  Managers and Settings administrators bypass that assignment restriction.
  Unassigned Call Center users can see the server's authorized sales branches.
  Users without branch assignment or Call Center access see no local bills.
  Server Allowed Sales Stores restrictions still apply when configured.
- Bill headers and lines are protected by global record rules, including direct
  ORM access, wizard details and printing. Assignment changes invalidate cached
  rules. Local bills are archived rather than physically deleted.

The existing token-scoped API endpoint and five-minute cron are reused. The module
upgrade explicitly enables that cron and sets its interval to five minutes. Deploy
the paired branch API correction before target-upgrading `ab_sales` on callcenter;
do not upgrade `base`. Translation updates support both `ar` and `ar_001`. No
migration hooks or historical imports are installed.

Stock lookup, customer operations, return eligibility checks and submission
continue through the existing branch API. Direct E-Plus access remains disabled
on callcenter. This change does not make new branch operations available offline.


### Automatic submission recovery (19.0.3.4.0)

If a sale/return API response fails, callcenter invokes `reconcile_operation`
using the original database/store identity and token. When the branch confirms
completion, callcenter repeats the original API method to obtain the stored
result with payload-hash validation; it does not create another bill. A proven
rollback preserves the original validation error and the draft for explicit
retry. An unavailable/busy branch keeps the bill and asks the operator to retry
the same bill later, without routine manual branch inspection.

Use **Bills → Retry Submission** for a retained sale. The branch handles all
external transaction checks. The five-minute cron and search refresh query
PrePending and Pending submissions by their original request tokens; they never
repost drafts.
Conflicting evidence and legacy returns without sufficient durable identifiers
remain blocked and require support rather than risking duplicate inventory or
cash changes. Customer-creation recovery is unchanged.

Deploy branch `ab_branch_api` 19.0.5.3.0 before callcenter `ab_sales` 19.0.3.4.0,
perform targeted upgrades/restarts, then retest Branch Connections. Tests use
disposable Odoo databases and mocked external writes; live deployment is separate.


Recovery diagnostics correction (19.0.3.4.1): callcenter preserves the original
submission error alongside any recovery failure. A reconciliation conflict is
not an E-Plus connectivity test. The branch correction in `ab_branch_api`
19.0.5.3.1 excludes invoice ID zero when the draft has no serial and reports the
specific reason for any remaining conflict. Keep using the original bill/token.
