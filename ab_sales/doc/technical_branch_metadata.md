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
