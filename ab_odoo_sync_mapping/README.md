# Branch upload receipts

Authenticated `/ab_odoo_sync/upload` requests are durably saved before their
successful response. `accepted` counts safely received rows, including duplicate
retries; `failed` and `errors` describe delivery, not later mapping/application.
`queued` counts receipt-processing jobs; it does not mean business data applied.
`ignored` counts exact duplicate receipts. The branch sender needs no protocol change.

Settings administrators can open **AB Odoo Sync → Upload Receipts** to inspect
receipt status, original JSON, processing details, and the associated upload
record's current application status. Original rows and their authenticated branch
identity cannot be edited or deleted. No receipt cleanup is scheduled.

Invalid metadata, protected source models, row branch mismatches, and conflicting
event IDs are quarantined without application. Corrected metadata must be sent
as a new event. Mapping errors are recorded as Processing Failed; after correcting
the mapping, use Retry Processing. This button also recovers a queued receipt
whose processing job has finished or failed; an active job is never duplicated.
Pending Mapping/application failures remain managed by the existing Received
Uploads and Apply Profiles screens. A receipt's linked upload record represents
the latest source revision, so its application status can change over time.

Authentication, approved hardware, model protection, and application validation
remain enforced. A storage or commit failure returns HTTP 503 so the branch
retains and retries its outbox. Invalid envelopes still receive HTTP 400.
Raw values are not included in receipt processing diagnostics or notifications.

Deployment: back up the active report database and addon, stop both Odoo services,
upgrade only `ab_odoo_sync_mapping`, then start both services. Verify an authorized
upload and an unauthorized upload before requeueing one production branch job.
Do not bulk-requeue the failed backlog until a pilot verifies durable receipt and
branch delivery completion. Do not run `-u base`.
