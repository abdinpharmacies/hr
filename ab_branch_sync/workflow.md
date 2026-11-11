# Inventory synchronization workflow — 19.0.5.1.0

## Ownership

Install ab_central_sync on central and ab_branch_sync on branches. Bills remain
in the branch for POS and cashier operations. Central owns the inventory ledger
and records the corresponding sale/return. Callcenter still calls ab_branch_api
on the branch. Cashier payments and accounting remain branch operations.
The branch does not install ab_inventory, ab_stock_integration, purchase receipt,
opening-balance or purchase-accounting modules. Staff enter all stock receipts,
opening balances and adjustments in central. Branch sales use the central snapshot
and durable local reservations; an unenrolled native store cannot post a sale.

## Independent replication

Branch Synchronization installs and runs without ab_odoo_replication or
ab_odoo_connect. Prepare the local branch identity, assigned stores, products,
units and other required master records before connecting. The ab_replica_db
model belongs to ab_store and remains the source of branch routing metadata.

When installed separately, ab_odoo_replication continues importing its configured
sales master data from central. Branch Synchronization does not extend or control
the replication engine. Stock snapshots, local reservations and outgoing
synchronization operations remain owned by Branch Synchronization; do not add
them to master-data replication jobs. Existing replication installations and job
activation settings are unchanged.

## Connection and stock

The only authentication credential is a standard Odoo user API key (RPC scope).
On central, assign the user the **Inventory Writer** role and explicit
**Inventory Stores**. Active users can access only the intersection of their
inventory stores, allowed companies, and the requested replica's sales stores.
The role is not granted to administrators automatically. Revoking the key or
removing the role removes transport access.

On the branch, enable developer mode and open Settings → Technical → Parameters →
System Parameters. Configure these existing keys directly:

| Key | Value |
| --- | --- |
| `ab_central_branch_connection.url` | Central HTTP or HTTPS URL |
| `ab_central_branch_connection.database` | Central Odoo database name |
| `ab_central_branch_connection.api_key` | Inventory Writer's standard Odoo user API key |

Then open Branch Synchronization → Operations and click **Connect to Central**.
The button reads the saved parameters, verifies access, and downloads the initial
stock snapshot. **Sync Now** delivers up to 100 queued, uncertain or retryable
protocol-3 operations and refreshes stock; its notification reports whether any
outgoing operations still need attention. Both buttons are available on an empty
Operations list and require a system administrator, including direct RPC calls.
The object-button handlers accept empty or multiple-record selections through
Odoo record-method dispatch; the connection and synchronization run once per click.
Synchronization managers retain their existing operation review/retry access.

Enrollment ignores cancelled native invoices only when cancellation records include
the actor, timestamp and a non-empty reason. Local stock allocations, payments and
posted returns still require reconciliation. Never delete invoices or journal rows
to enable a connection. For a missing journal, restore verifiable central evidence
first; cancel abandoned invoices only after reviewing central counterparts and
using native cancellation/reversal workflows on the affected installations.

Changing, creating, renaming or deleting a connection parameter clears connection
authorization and stock readiness. Click Connect to Central again after editing
the target or API key. Unchanged values and unrelated parameters do not reset the
connection. The module maintains these parameters; do not configure them manually:

| Key | Purpose |
| --- | --- |
| `ab_central_branch_connection.authorized` | Central connection authorization |
| `ab_central_branch_connection.ready` | Initial stock snapshot readiness |
| `ab_central_branch_connection.origin` | Connected branch database identity |
| `ab_central_branch_connection.stores` | Authorized store codes |
| `ab_central_branch_connection.connection_status` | Connection and stock synchronization status |

The optional `ab_central_branch_connection.pos_sync_interval_seconds` controls the
POS refresh timer (default 10 seconds). Changing this interval or internal state
does not clear authorization.

For an existing development installation, rename the old `ab_branch_sync.url`,
`ab_branch_sync.database`, and `ab_branch_sync.api_key` keys in System Parameters
to the corresponding `ab_central_branch_connection.*` keys, preserving their values.
If a custom `ab_branch_sync.pos_sync_interval_seconds` exists, rename it too to
preserve the interval. Then click **Connect to Central** to regenerate the five
module-maintained parameters and download stock. Old parameter names are no longer
read; no automatic migration or fallback is provided. Renaming keys does not
change database UUIDs, replica serials, snapshots, or operation records.

There is no pairing code, per-replica secret, service-user login, CA bundle, or
certificate verification step. HTTP and HTTPS are supported; HTTPS certificate
verification remains disabled as requested. The configured replica identity
(`db_serial` in the Odoo configuration file) and replicated store assignments
remain routing/access metadata, not credentials.

Master-data replication uses a separate connection through `ab_odoo_connect`:
`server_address`, `server_db`, `server_user` and encrypted `server_password`.
Its URL/database may point to the same server, but its credentials and purpose
are independent. Do not replace those keys with the inventory synchronization keys.

Central posts as the authenticated Inventory Writer. The branch employee remains
bill metadata, and its replicated employee/profile must exist when employee
sessions are installed. A server-only trusted replay context authorizes this
transport without a central employee PIN or POS service-user configuration.
Ordinary branch POS and cashier session checks remain in force.

Before approving a connected sale, refresh its products from central. Network
outages and central HTTP 5xx failures permit the last complete snapshot to be
used. Authentication/business errors do not select offline fallback. A first
complete stock snapshot is mandatory. There are no offline quotas or cache-age
selling limits. Existing shortage and business-validation rules remain in force.

Sale approval and its immutable outgoing inventory operation commit together.
An immediate post-commit delivery attempt checks central status before submission;
uncertain outcomes retain the original token. Branch bill inventory status is
separate from cashier status. A locally pending/saved bill is not proof of central
inventory acceptance. The bill form and POS status API expose inventory state,
central bill reference, and diagnostic details. Existing callcenter responses
continue exposing sync_state and sync_message alongside their branch bill reference.

## POS opening and connection status

The branch POS header shows a compact central connection tag. Once a store and,
when installed, an active employee session are available, it synchronizes in the
background: verify central identity/protocol, deliver up to ten queued protocol-3
inventory events for that store, then atomically replace that store's full stock
snapshot. Existing retry/hourly jobs handle the remaining work. Legacy protocol-2
events are not replayed. POS requests cannot operate outside the current replica,
authorized stores, user access, or employee authorization.

The tag reports syncing, online, offline, or needs attention. A connection check and full store resync run through setInterval every 10 seconds
while the POS is open. The system parameter
`ab_central_branch_connection.pos_sync_interval_seconds` controls the interval in seconds
(default 10; invalid/nonpositive values fall back to 10). Active requests do not
overlap. The response updates the timer if the parameter changes. Recovery from an
offline/failed sync installs a fresh snapshot; clicking the tag retries manually.
Successful downloads refresh displayed product and line availability without
changing draft quantities or selected prices. Timeouts/central server errors keep
the previous cache; authorization and invalid snapshots are reported separately.
Store/session changes trigger a new scoped sync and discard stale UI responses.
Timers are removed when the screen closes. Payment and cashier flows are unchanged.

## Immediate stock display after sale approval

A confirmed branch POS response includes absolute sellable balances for its line
products: the last central snapshot minus durable local reservations. This read
never contacts central and works offline. The same feedback is available for
idempotent retries and recovery after a lost response. The stored central snapshot
is not decremented; its acknowledgment watermark/serials prevent double deductions
when central later includes the sale in a new snapshot.

On the first confirmed response, the branch POS updates product cards and open
draft lines for that store immediately, invalidates older balance/search reads,
and refreshes visible stock/filter results from the branch. It replaces absolute
balances rather than subtracting client-side quantities. Repeated confirmations
cannot deduct again, other stores are untouched, and draft quantities/prices and
cashier/payment processing remain unchanged.

## Product units and inventory basis

Product, purchase, audit, and sales units use `ab_product_uom` within the
product's category. The active reference unit has factor 1. Inventory movements,
central snapshots, and branch reservations are measured in that reference unit,
with up to eight decimal places. A purchase receipt or POS sale converts its
selected unit through the canonical factor. Central source prices and costs are
converted from the source's purchase unit to the reference unit before sale
price matching. T500 BOX has factor 1, so one BOX adds or deducts one reference
unit. New central allocations record that reference unit in `uom_id` and
`stock_uom_id`.

The retired `ab_uom` and `ab_uom_type` models are no longer used. The backed-up
experimental T500 ledger and old bill stock evidence were normalized once to
preserve 21 BOX in central stock. Cashier payments and monetary totals were not
changed. A fresh snapshot with `stock_basis=product_uom_reference` is required
before selling from the cache; normal offline fallback then applies.

## Delivery and central posting

New operations use protocol 3 at /ab_central_sync/v3/. Central commits stock,
its bill representation, and the operation result atomically. Duplicate tokens
return the same result; modified payloads are rejected. The API key, Inventory Writer role, active user, company, replica and explicit
inventory-store scope are checked on every request.
Central selects actual stock batches; agreed quantities, prices, promotions and
totals must still match. Inventory conflicts remain visible for reconciliation.

Independent bills do not wait for unrelated serials. Return/payment-status/
cancellation events depend on their original accepted bill; returns also depend
on its collected status. Protocol 3 cashier events only update the central bill
status through its existing transition; they do not create central payment or
accounting records. Protocol 1/2 endpoints reject requests with HTTP 426; they cannot post payments.

Delivery retries run every minute. Full stock refresh runs hourly. Successful
stock posting refreshes affected products; connection failures mark the connection
for a complete refresh on recovery. Sync Now delivers queued operations then
refreshes stock. Older installed noupdate retry jobs need their interval reviewed
during the bounded pilot cutover; fresh installs receive the one-minute schedule.
When a development branch database is assigned a different replica, retries skip
operations for stores outside the current replica. Historical operations remain
in the journal for reconciliation and are never replayed as the new branch.

## Snapshot replacement

Download all pages inside one transaction/savepoint. Hold the local stock-scope
lock and require a consistent central stock revision. A partial or changing
snapshot rolls back, preserving the previous cache. Complete replacements zero
cached products/batches omitted from the new snapshot, without deleting records.

Availability is the latest snapshot less local sale deductions not represented
in that snapshot. A contiguous acknowledgment watermark plus sparse accepted
serials accounts for independently posted bills beyond rejected predecessors.
Acceptance alone does not release a deduction: the installed snapshot must
acknowledge it. If central batch selection changes, pending quantities also reduce
remaining product batches conservatively. Concurrent tills share the same store
lock. Returns/cancellations increase availability only after central stock refresh.

## Manual Retry and existing operations

In branch Branch Synchronization, open a protocol-3 outgoing operation and click
Retry. It immediately checks central status. Missing or retryable operations are
submitted immediately; rejected operations are retried on central with the same
immutable payload, token and hash after their underlying issue is corrected.
An already accepted operation returns its existing central bill without repeating
stock deduction. The result is shown and the view reloads. An offline attempt
remains uncertain with a visible warning and is eligible for the minute retry job.

Protocol-2 pilot rows remain immutable and require manual reconciliation;
the new Retry button does not convert or replay them. No bills, stock movements,
payments or journal identities are deleted by the connection reset. Old pairing
credentials and connection settings are cleared during this development cutover;
enter the new user key and reconnect before selling. Central must be upgraded
before branch. No production migration hook is shipped.

Update this workflow whenever ownership, transport, snapshots, recovery, or
integration behavior changes. Keep both worktrees' role documentation aligned.
