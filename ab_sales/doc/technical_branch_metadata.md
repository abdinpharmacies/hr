# Technical branch metadata

New sale submissions include `metadata_context` version 1 in the frozen branch
wire payload. It contains the source `database.uuid`, descriptors for every
submitted header field, and matching descriptors for each line (excluding the
transport-only `uom_factor`). The sender derives field types, related models and
source IDs from its ORM after editable-field filtering. Browser-provided context
is not copied into the wire context.

Many2one source IDs use `[id]` or `[]`; Many2many uses unique source IDs. Supported
Many2many input is an ID list or set/link/unlink/clear commands against the new
snapshot. Create/update/delete commands are rejected. The wire values retain
stable references for ordinary branch resolution; source IDs are reporting data.
Booleans/numbers/strings retain their types, selection values remain technical
keys, and date/datetime values become ISO strings (UTC for datetime, null if unset).
One2many and binary input are unsupported.

Only allowlisted fields absent from the receiving branch model enter its
technical metadata. Fields that exist there follow ordinary validation and
business logic. Missing contract or invoice-discount functionality still rejects
nonempty values. Metadata is visible only to technical administrators, not branch
users; optional sales-channel installation on the branch is unnecessary.

Deploy the updated `ab_branch_api` receiver before this sender. Upgrade only the
target modules and restart workers. Preserve existing frozen retry payloads;
legacy requests needing source IDs must use rejected-bill correction and a new
revision. Do not patch frozen payloads or automatically retry live bills.

Reporting must identify records using source UUID + related model + source ID.
Database clones share UUIDs until deliberately assigned a distinct identity and
must not be imported as independent production sources with a duplicate UUID.


## Delivery descriptor rejection recovery

The delivery addon removes notification fields when consent is off. It must also
remove their descriptors. Upgrade `ab_sales` and `ab_sales_delivery_tracking` on
callcenter and restart its workers to activate this fix.

For an already rejected request with orphaned `delivery_notify` and
`delivery_instructions` descriptors, use **Correct bill**, then **Submit correction**.
The server confirms rejection, cleans only descriptors for omitted delivery
fields, and freezes the next revision with the original request in audit history.
No quantity or price change is required for this repair. Ordinary **Retry** still
replays the original frozen payload, and an already frozen correction replays
without incrementing the revision again. No live bill is automatically submitted.

## Promotion source identity

For a new sale with a selected promotion, a receiver advertising
`submission_source_identity: 1` receives a top-level `source_db_serial` derived
from the callcenter server's positive integer `db_serial` configuration. The
existing `metadata_context.source` UUID and promotion reference are retained.
Browser-supplied source identity is ignored. Destination RPC/store routing and
all other promotion eligibility checks remain unchanged.

Ordinary sales do not require this new source configuration. Older receivers
retain the legacy payload and validation behavior, including promotion sales;
a promotion allowed only for callcenter may still be rejected there.

The receiver must include the source-identity implementation and promotion fixes
through `4e2e098956049f0a66c7bea0ce24bcba840f9eca`, with the earlier
`ab_branch_api` schema upgrade applied. The advertised capability alone does not
prove those promotion fixes are installed. The receiver API user must have the
Call Center role, and the source serial must identify exactly one active replica.

Frozen retries never gain or refresh source identity. A confirmed rejected
correction may add missing identity in its next revision, even without changing
quantities or promotion; previous identity and audit history are preserved.
Lost-response retries replay that revision unchanged. Confirmed-rejection draft
recovery creates a replacement attempt using the new submission behavior.

Deploy the callcenter code, upgrade only `ab_sales` to load translations and
module metadata, then restart its workers. This change does not alter returns,
grant roles, repair production data, or automatically replay any submission.
