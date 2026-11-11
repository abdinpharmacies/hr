# Delivery Job Failures And Retries

## Recent relevant commit

- Commit: `390db7fa1d233de540f50269fabba550ad911c51`
- Author: emadco88 <emadco88@gmail.com>
- Date: 2026-09-25
- Original subject: `ab_odoo_sync_upload/ FIX User-Agent cloudflare issue`
- User-facing changes: Send an explicit application User-Agent to the report API.

Files changed:

- `ab_odoo_sync_upload/changelog.d/2026-09-25-report-user-agent.md`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`

## Current changes before commit:

- Successful delivery finishes the queue job; configuration, authorization, invalid-response, and other permanent delivery failures now fail the job instead of returning a normal failure dictionary to the runner.
- Connection failures, timeouts, HTTP 408/429, and HTTP 5xx retry indefinitely after 1 minute, 5 minutes, 15 minutes, then hourly; a longer valid Retry-After is honored. Certificate verification failures require intervention.
- Partial batches preserve accepted records as Sent and fail the job for the rejected records. Manual retry sends only records still eligible for delivery.
- Persist outbox delivery status, attempt counts, and errors in a dedicated delivery transaction before raising queue exceptions. The caller's business transaction is never committed by this transaction.
- Add an indexed delivery-job UUID and atomically assign records to jobs. The scheduler selects only unowned records, preventing competing retries and starvation by failed records already owned by a job.
- Retry and Send Now reuse an existing terminal job, leave active/delayed jobs alone, and create a replacement for a deleted job only after an explicit manual action. Existing done jobs remain historical records.
- Legacy jobs claim unowned records safely and skip another job's records. A legacy job without explicit batch arguments keeps its original claimed batch on retries.
- Keep raw batch delivery private to Python callers and require queued sender execution to match a started job and its stored arguments.
- Add an upload-scoped controller override that skips dependency processing after postponement: the installed queue runner otherwise accesses its closed retry-storage cursor. Successful jobs still release dependents; the shared queue_job addon is unchanged.
- Show the delivery-job UUID in the outbox form, translate new labels/errors into both Arabic catalogs, and bump the module to `19.0.1.6.0`.

Validation:

- Fresh installation and targeted module upgrade passed in an isolated local database with scheduled jobs disabled.
- Actual queue-controller execution passed for success, increasing indefinite retries, permanent 401/403/404 failures, HTTP 408/429/5xx, Retry-After parsing, timeout, certificate failure, unexpected client exceptions, missing configuration, and malformed responses.
- Partial delivery retained successful receipts across job rollback; manual retry sent only the rejected row. Failure metadata and attempt counts persisted while an unrelated uncommitted marker rolled back.
- Lost-response retries preserved event UUIDs and source revisions. Simulated worker interruption after receipt commit did not resend accepted records.
- Concurrent overlapping enqueue transactions claimed each record once using Odoo's serialization retries. Scheduler/manual requests did not duplicate or accelerate active jobs.
- Cancelled jobs stayed held, deleted-job recovery required manual action, disabled outbox records were skipped, and both explicit-batch and no-argument legacy jobs respected ownership.
- Snapshot capture plus job creation rolled back with the business transaction. Raw delivery was inaccessible through RPC.
- Real local HTTP queue endpoint returned success when postponing without a closed-cursor error, kept dependents waiting until delivery succeeded, and persisted terminal failures in both the queue and outbox.
- Exported POT references, both Arabic PO format checks, Arabic runtime field translation, Python/XML syntax, and diff whitespace checks passed.

Deployment:

- Commit/push/pull manually. With branch Odoo services stopped, upgrade only `ab_odoo_sync_upload`, then start both services to load the new field, queue settings, and controller override.
- The upgrade does not reclassify old done jobs, replay the backlog, or enable the upload scheduler. Legacy failed outbox records without ownership can be queued once after deployment.
- Changes are local only; no production services, records, or scheduled actions were changed during implementation.

Files changed:

- `ab_odoo_sync_upload/__init__.py`
- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-25-delivery-job-retries.md`
- `ab_odoo_sync_upload/controllers/__init__.py`
- `ab_odoo_sync_upload/controllers/queue_job.py`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/__init__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_transport.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/upload_views.xml`
