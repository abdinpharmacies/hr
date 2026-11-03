# Central synchronization, version 2

Only the previously approved `ab_central_sync_operation` journal is a new model.
Enrollment extends `ab_replica_db`; cached balances extend `ab_sales_inventory`.
Sales, returns, allocations, reversals, payments and inventory movements reuse
the existing models and business methods. Central synchronization does not depend
on `ab_branch_api`. Purchasing and other inventory workflows are unchanged.

## Deployment status

The `ab_central_sync` v2 source changes have been copied into the `branch19`
and `dev-central19` worktrees at the user's request. No database upgrade,
service restart, enrollment or configuration change was performed for this transfer.
The isolated development copies are retained.

Both `ab_central_sync` and its required `ab_sales_inventory` extension hooks
have been transferred into these worktrees. Database upgrades and activation
remain pending. The optional branch/callcenter adapter changes remain in isolated
development worktrees. Keep branches used by the running callcenter outside the
central cutover until those adapters and their stored reference fields are ready.

Existing v1 Branch/Central role settings are not inert: upgrading these installations
activates v2 readiness checks. Schedule a coordinated cutover; an upgrade without
enrollment and initial stock readiness can block sales. This transfer does not reset
existing roles or inventory backend settings.

## One-time setup

1. Install the same `ab_central_sync` version on central and each participating
   branch, together with the updated `ab_sales_inventory` extension hooks.
2. On central, select the Central installation role in Settings. Under Central
   Synchronization → Branches, reuse each existing replica's DB serial and store
   assignments. Replicated product codes, units, customers, employees, contracts,
   promotions, user logins and store service users must already match.
3. Reconcile central opening balances and review return history. Confirm the
   review on the replica record. No branch opening stock ledger is required.
   Generate a single-use pairing code, valid for 15 minutes.
4. On the branch, select Branch, enter the central HTTPS URL, database and pairing
   code, then Connect to Central. URL/database can be provisioned as shared system
   parameter defaults. The service generates the credential; there is no peer JSON
   or manual per-user mapping. The branch's existing replica/store assignments
   must match central, and open sales/returns must be completed before enrollment.
5. Download the initial stock snapshot before selling. Missing catalog identities
   stop the download. Enrolled sales use central inventory automatically; there is
   no E-Plus fallback. Pairing is per database installation, not per login/session.

The role remains disabled when unset. Enrollment uses `database.uuid`; a copied
branch database cannot submit as another installation. Store codes identify the
transport scope. Administrative reversals additionally require an explicit store
assignment on the central user. Other operations require the store service user
and an authorized replicated employee profile. Business posting runs as that user,
not as superuser, and does not grant groups.

Settings stores the URL, database and generated API credential in system
parameters. Central stores only credential/code hashes on the existing replica.
Secrets and installation status are excluded from normal master replication.
Revoke Connection disables the credential. Generate another code and pair again
to rotate it; already queued payloads retain their original operation identities.

## Operation and stock flow

- Branch approval commits its sales document and immutable JSON journal entry
  together. It creates no branch stock movement/allocation records. Existing
  approval, pricing, contract, promotion, shortage and employee rules still run.
- A post-commit callback submits immediately. Uncertain delivery is checked with
  central before replay. A cron retries every 15 minutes; Sync Now is also available.
- Branch availability is the cached central balance less outgoing sale batch
  reservations newer than that product's snapshot watermark. An acknowledgment
  alone does not remove a reservation. Pending return/cancellation credits are
  unavailable for resale until central includes them in a new snapshot.
- Central locks the store and processes each origin/store serial in order. The
  existing business methods create central allocations and call
  `ab_inventory_process.inventory_write()`. Batch references are opaque central
  IDs in JSON; branches do not need matching source records or source XML IDs.
- Incoming acceptance, inventory effects and the result commit atomically.
  Duplicate tokens/content return the original result. Changed content, stock,
  pricing or promotion eligibility cannot silently replace an agreed operation.
- Snapshot balance, revision and accepted serial watermark are read under the
  posting lock. Per-product watermarks make paginated/partial refreshes safe.
  Accepted operations refresh affected products; periodic synchronization refreshes
  the catalog. Stale snapshots cannot overwrite a newer revision/watermark.

Endpoints are POST `/ab_central_sync/v2/{pair,connection,submit,status,reconcile,snapshot}`.
Requests use the configured database header and generated Bearer credential;
pairing authenticates with its single-use code. HTTPS is required by the sender,
redirects are refused, and requests are limited to 2 MB. Version 1 is explicitly
rejected with HTTP 426; existing v1 payloads must not be silently relabeled as v2.

## Callcenter compatibility

The optional `ab_branch_api` adapter activates when the installation role is
Branch. Installations with central synchronization disabled retain their existing
methods and E-Plus responses. Selecting Branch requires successful enrollment
and the initial stock download before sales can continue. Central does not install
or call `ab_branch_api`.

Upgrade the callcenter client before enrolling its branches. Native responses
carry explicit native invoice/return/payment references; E-Plus posting IDs remain
zero. Native returns use dedicated endpoints and the existing employee profiles.
The client stores native references separately and prevents native/legacy invoice
number collisions from mixing return histories. Request tokens, rejected-request
corrections, store checks and duplicate protection remain in force. Stock, customer
lookup and sales-day reads use Odoo on enrolled branches.

## Recovery and cutover limits

Managers can inspect journal errors, retry an incoming rejection after correcting
its cause, and retry the matching outgoing operation. Accepted payloads are
immutable and cannot be reapplied. Unresolved serials block later operations.
Check Missing Serials reports missing/failed serials in windows of up to 1,000.
The branch list shows last contact and unresolved received operations; an offline
branch's untransmitted backlog is available in that branch's own journal.

Historic sales are not automatically reposted or imported. Returns without a
reviewed original synchronized sale are blocked before approval and require
history review/import through the existing sales structures. Enrolling a branch
is not authorization to replay old stock effects. Resolve catalog, opening-balance,
permission and return-history readiness before cutover. Do not switch an enrolled
installation with synchronization history to a different role.

Before upgrading, check for multiple `ab_sales_inventory` rows for the same
store/product. The updated cache constraint requires one row per store/product,
including products without E-Plus IDs. Investigate any duplicates before cutover;
this module does not delete or merge existing rows automatically.

## Acceptance checks

Use disposable databases first: pair once; restart; submit online; disconnect;
submit offline; restart again; reconnect and retry. Confirm that branch inventory
movement counts stay unchanged and central stock changes exactly once. Test a
lost acknowledgment, stale snapshot, duplicate/concurrent submit, missing serial,
rejected operation, another store's credential, partial return and cancellation.
Check contract/promotion totals and both Arabic language codes. For callcenter,
test one branch with synchronization disabled and one enrolled native branch, including
rejected-sale correction, saved-sale status refresh, return preview and refund.
