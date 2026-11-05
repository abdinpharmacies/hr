# Synchronization workflow — version 19.0.3.0.0

Updated 2026-11-05. This is a clean-install architecture. Existing v2 databases
must not be upgraded or have their old addon uninstalled as a shortcut to this split.
No production data migration is provided.

## Modules and communication

Exactly two synchronization modules are provided. Install `ab_central_sync` on
central, and `ab_branch_sync` on branches. Do not install both on one database.
The installed module determines the role; there is no role selector.

Callcenter → branch `ab_branch_api` → branch sales business methods →
`ab_branch_sync_operation` → central HTTP(S) `/ab_central_sync/v2/` →
`ab_central_sync_operation` → central inventory business methods.

Direct branch POS uses the same branch business methods and outgoing journal.
Callcenter never receives central credentials or contacts central directly.
The branch API is optional for direct POS; central has no branch API dependency.

## Enrollment and stock

On central, configure the replica identity, selected stores and reviewed opening
balances/return history. Generate a single-use 15-minute pairing code. On the
branch, configure matching replica/store scope, HTTP or HTTPS URL, central database and
pairing code; connect and download the initial snapshot. Credentials are hashed
on central. Branch configuration uses `ab_branch_sync.*` parameters. Master data
must already be replicated, including employees, products, units and customers.

Until the full initial download succeeds, selling is blocked. Afterwards, products
without initialized central cache rows have zero sellable stock, even when an old
legacy balance row exists. Legacy quantities are never substituted for central
stock. Availability equals cached batches minus outgoing sale reservations newer
than each product's accepted-serial watermark. Acknowledgment alone does not release
reservations. Returns/cancellations add availability only after a central snapshot.

## Transaction lifecycle

Drafts remain local. Confirmation atomically creates the branch sale and immutable
journal payload with origin UUID, store, token, hash and contiguous serial. No
branch inventory movements or relational allocations are posted. The post-commit
sender checks status before submission. Automatic retries run every 15 minutes
(up to 20 due operations); Sync Now processes up to 100 operations.

Central authenticates credentials and store ownership, locks the store, and requires
all earlier serials to be accepted. Posting uses the replicated service user and
authorized employee profile. Sale allocations, pricing, promotions and totals
must match; rejected posting effects roll back. Duplicate accepted tokens return
the original result. Changed payloads cannot replace an accepted operation.

Events: sale confirmation, sale settlement, native return approval, refund
settlement and pending-sale cancellation. Existing cashier workflows retain
collection/refund ownership: API return submission approves a pending return,
without automatically issuing a refund. Purchasing is outside this transport.

## Callcenter contract

Capabilities are store-specific. Synchronized stores advertise `central_inventory=2`
and native return methods. Legacy stores retain their existing methods and responses.
Native responses carry `inventory_backend=central`, explicit native invoice/return/
payment references and zero E-Plus posting IDs. IDs are interpreted within their
branch/store and backend; native and E-Plus return histories remain separate.

Sale responses include `sync_token`, `sync_state` and a sanitized `sync_message`,
separate from the business status. Branch acceptance is not proof of central
posting. Central rejection does not reopen an approved local bill for editing.
Request tokens and revisions still govern corrections rejected before approval.
Callcenter stores/displays central posting status and polls the branch for updates.
Local-only customer creation is blocked on synchronized API stores until the
customer catalog is replicated. Native return preview and submission use dedicated
methods. A pending return is collected/refunded through the existing cashier flow.

## Rejected sale recovery

Correct a fixable cause, Retry on central, then Retry the branch operation and Sync
Now. For irreplayable batch allocations, post a reviewed matching central native
sale through normal business methods and leave it pending. A central administrator
uses Reconcile Rejected Sale to link it with a mandatory reason. Store, line order,
products, units, quantities, stock deductions, customer/header, promotions and
financial totals must match. Existing payments, returns or another journal link
are rejected. Branch and actual batch/cost evidence, reason, administrator and time
are retained. No stock is posted twice and the original payload remains immutable.

Branch Retry observes acceptance and later settlement/return/cancellation events
use the linked central sale. There is no blind serial skip. If matching posting
evidence is unavailable, correct the business discrepancy before accepting it.

## Maintenance and rollout

Update this workflow in the same change as enrollment, protocol, permissions,
stock availability, lifecycle, recovery or integration behavior. Both role copies
must agree on version-2 wire serialization and hashes; verify against common
external fixtures. Fresh isolated pilot databases are required. Upgrade the
callcenter client before enrolling its operational branch. Existing databases and
v2 credentials/history remain untouched until a separately approved cutover.

## Certificate-independent transport (branch 19.0.3.0.1)

Settings → Branch Synchronization accepts HTTP or HTTPS. For a trusted LAN/VPN,
use `http://CENTRAL_HOST:PORT`: no certificate or CA registration is required.
For HTTPS with a self-signed/untrusted certificate, uncheck Verify TLS Certificate
and save/connect. Verification remains enabled by default; an optional CA bundle
is used only while verification is enabled. Disabling verification ignores the
CA bundle. There is no automatic fallback after a TLS error and no redirect following.
HTTP is unencrypted; unchecked HTTPS does not authenticate the server certificate.
Pairing, Bearer authentication, database/store scope and initial stock readiness
remain mandatory in both modes. This changes only branch-to-central transport.
