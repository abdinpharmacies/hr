# Direct branch uploads

Authenticated `/ab_odoo_sync/upload` requests store valid rows directly in
`ab_odoo_sync_upload_record` before acknowledging delivery. Each branch, source
model, and source record ID has one row containing its highest received revision.
Newer revisions replace the payload and invalidate older queued application
generations. Identical retries and older revisions do not reset application state.
Conflicting content for the same revision or detectable reuse of a current event
UUID is rejected. Historical event IDs are not retained after replacement.

Missing target models or mapping profiles do not block delivery: uploads remain
Pending Mapping. Inactive profiles behave as missing profiles. Valid uploads for
disabled profiles remain Pending; Raw Only and Ignore retain existing handling.
Malformed rows, protected models, and mismatched branch identities are rejected
individually so the sender retains them for correction and retry.

The response shape is unchanged. `accepted` includes stored rows and unchanged
retries/older revisions; `ignored` counts unchanged rows. `failed` and indexed
`errors` describe rejected delivery rows, not mapping failures. `queued` now
counts apply jobs. Storage or commit failures return HTTP 503 without an
acknowledgement; invalid envelopes return HTTP 400. Concurrent storage conflicts
retry delivery rather than acknowledging unstored data. Normal branch senders
need no protocol changes.

**Automatically Queue Apply** controls automatic application jobs only. Valid
uploads are always stored. Only active Mirror Sync Model or Business Model
profiles with this switch enabled create apply jobs. A non-database scheduling
failure leaves the stored upload pending with a retry message; a database failure
rolls back delivery. Existing apply feeders and Queue Apply/Replay Failed can
retry stored uploads. No profile is automatically created while accepting rows.

**Reapply Mapping** runs immediately without jobs, even with automatic queuing
disabled. It uses the current active apply-capable profile, mappings, and per-upload
overrides. Successful selected records are retained when another fails; the
notification reports applied, partial, failed, and busy/skipped totals. Busy records
can be retried. Large selections take longer, and request-level failures can roll
back the request. No per-record commits or background fallback are used.

On passive reporting targets with Odoo access logging disabled, source
`create_uid`, `create_date`, `write_uid`, and `write_date` can be mapped as stored
source data even though the reporting UI remains readonly. User fields resolve
through existing branch-scoped identity records and `ab_users` source-ID
placeholders, not local Odoo user IDs. Ordinary Odoo
models and other readonly/computed fields retain their mapping protections.

An enabled **Ignore** mapping handles its source field without writing a target
field or marking the upload Partially Applied. Ignore mappings need no target
field and cannot be Required. Disabled mappings are intentionally ignored; per-upload
overrides take precedence. Archive operations also honor explicit ignores.
The four sales/returns profiles initially map the four audit fields and ignore
`activity_ids`, `message_follower_ids`, `message_ids`, and `push_message`.
Other unhandled fields, including `replication_posted` and `return_client_token`,
still cause partial status. Existing results change only when reapplied.

Turning **Sync Enabled** off selects Ignore and clears Required. Turning it on
infers a compatible type from the current source/target metadata and relation
settings, without storing a previous type. Scalars use Direct Value; supported
relations use source-ID sync, or stable-key mapping when both keys are configured
and permitted. Source-user and report-owned relation restrictions still apply.
Missing, incompatible, one-to-many, or protected fields remain Ignore for manual
configuration. Mapping Type is editable only while enabled. Explicit types sent
for enabled mappings are validated normally. Target and relation-key settings are
preserved while disabled; Required must be selected again if needed.

The 19.0.1.7.2 upgrade normalizes existing disabled mappings and overrides without
queuing feeders or reapplying uploads. Reapply selected uploads to refresh their
stored skipped-field lists and application status.

The legacy receipt model is removed in 19.0.1.7.0. Its bounded upgrade cleanup
deletes receipt-specific jobs and metadata and drops its table, without migrating
any receipt data. Finish any manual preservation before upgrading. Other upload
records, mapping settings, identities, and business tables are retained. No
automatic vacuum, retention task, or historical replay is added.

Deployment: prepare a database backup, stop intake and job workers, and upgrade
only `ab_odoo_sync_mapping`. Preserve the runner's previous stopped state when
restarting Odoo. Verify direct delivery, model/table removal, and queue policy.
Do not run `-u base` or bulk replay the backlog as part of deployment.
