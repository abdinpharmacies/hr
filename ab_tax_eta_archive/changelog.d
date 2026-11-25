Current changes before commit:

- Fix the HTTP wrapper ignoring raw_response: keep package ZIP and 204 responses out of JSON parsing, request binary content, and preserve safe nested/flat error codes, targets and correlation IDs.
- Poll documented, paginated package statuses before downloads. Distinguish preparing/available/failed/expired/missing states, recheck status after 400/404, and renew only confirmed expired requests with retained ID history and a two-renewal bound.
- Replace the generic package-or-new diagnostic with package ID, window and imported offset. Retain package IDs and archive rows when a request is missing or fails.
- Prioritize file dates when details/retrieval finish and pick up existing waiting or unverified files independently of the older sweep cursor. Add targeted Generate Files, scheduled retry cooldowns and independent category outcomes.
- Validate actual XLSX data rows and file-content digests before cache reuse or delivery. Rebuild header-only/invalid files from archived rows, verify newly generated files, expose File Rows and preserve valid sent files without duplicate revisions.
- Add paired Arabic labels in both catalogs, update standalone regression tests and bump to 19.0.1.1.1.

Files changed:

- ab_tax_eta_archive/__manifest__.py
- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_package.py
- ab_tax_eta_archive/models/eta_retrieval.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/views/eta_views.xml

Validation (2026-11-25):

- Passed 38 integration tests in 4.951 seconds. Regression tests cover the actual HTTP wrapper with ZIP/204 responses, safe 400 diagnostics, status pagination, expired/missing/failed packages, bounded renewal, old scan cursors, real XLSX data/UUID/VAT cells, header-only repair and valid sent-file reuse.
- Targeted Odoo 19 upgrade passed in eta_review_20261125. All HTTP is mocked; the live cause of package 205882's HTTP 400 cannot be determined from the correlation ID alone.
- Arabic entries were merged from a fresh Odoo POT and passed Babel checks. Runtime translation checks cover the new File Rows label. GNU msgfmt remains unavailable locally.

9101eed48d32a3427c5671d40a35e7d6219b61c0 - yahyazakaria22 - 2026-11-25
fix: make ETA retrieval resumable and daily exports reliable


- Persist page/window checkpoints, distinguish Partial/Error from completed days, retain diagnostics and remove forced completion progress.
- Enforce Cairo midnight and a configurable safety delay (default 12 hours), including fractional-second boundaries and complete-day export readiness.
- Align receipt retrieval with submission dates while preserving issue-date exports. Enable historical packages with contiguous adaptive windows, bounded polling and resumable imports. Preserve old checkpoint evidence and archived data.
- Remove receipt hourly probes and invoice page-20 restarts; add submission-window indexes, connection reuse and bounded HTTP retries/token refresh.
- Add retrieval queue/operation and shared-credential search advisory locks, retain detail/file/delivery locks, and use adjustable five-minute scheduling defaults.
- Persist independent waiting/details/empty/error/generated file outcomes, retry missing categories, and retain sent revisions. Add the icon, Arabic translations/references in both catalogs and version 19.0.1.1.0.

Files changed:

- ab_tax_eta_archive/__manifest__.py
- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/__init__.py
- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_dashboard.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_package.py
- ab_tax_eta_archive/models/eta_policy.py
- ab_tax_eta_archive/models/eta_retrieval.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/static/description/icon.png
- ab_tax_eta_archive/static/src/js/eta_dashboard.js
- ab_tax_eta_archive/static/src/xml/eta_dashboard.xml
- ab_tax_eta_archive/views/eta_views.xml

Validation (2026-11-25):

- Clean installation and targeted upgrade passed in isolated Odoo 19 database eta_review_20261125 with scheduled workers disabled. Upgrade snapshots preserved documents, raw/detail content, checkpoints, errors, a sent file and a custom interval.
- Passed 27 standalone integration tests outside the production addon, covering completion, overlaps, partial failures, long ranges, cutoff/DST boundaries, packages, late submissions, retries, file regeneration and runtime Arabic.
- A real Odoo cron callback with mocked HTTP committed page one, retained it after page-two failure and resumed successfully. Sparse receipt-day requests decreased from 24 hourly probes in the prior source to one measured request.
- No live ETA or Telegram requests were made. Preproduction must verify account limits, package date basis/precision acceptance, worker termination and production throughput. GNU msgfmt is unavailable; Babel and actual Odoo translation runtime checks passed.

f0e12dacfc7ef828363c325527a6efe574c86c3a - yahyazakaria22 - 2026-11-16
fix: decouple ETA file generation and improve retrieval performance


- Separate local Excel generation from Telegram uploads with an independent, resumable generation job. Generate every ready archive date regardless of the Telegram delivery start date or four-day send wait.
- Keep delivery date limits on sending only; validate that saved files still match their complete source rows before sending, retain explicit manual requests and preserve sent revisions when source data changes.
- Track source update timestamps and row counts to reuse unchanged files without rebuilding them; reuse Excel style objects rather than allocating fonts and alignments for every cell.
- Fetch only fields needed for UUID detail updates, wake detail jobs when search imports progress and wake generation after details become ready. Target 0.55-second raw-request spacing while retaining Retry-After cooldowns, day/type order and duplicate-run guards.
- Give details, local generation and delivery independent task locks. Isolate malformed file data so one failing date/category does not stop other ready files.
- Add English/Arabic labels for the generation/delivery jobs, generation scan date and source timestamp in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

Validation (2026-11-15):

- Targeted ETA upgrade passed in isolated eta_validation_20261115 with alternate ports and cron disabled. Exported the Odoo 19 POT, validated both PO catalogs with Babel and verified the new generation action in ar_001. GNU msgfmt remains unavailable locally.
- Passed 11 end-to-end groups using actual XLSX files and mocked HTTP: independent task locks, generation outside delivery limits, pending-detail holds, malformed-data isolation, unchanged-file reuse, delivery bounds/deduplication, stale-file safety, numbered corrections, day/type detail order, cached tokens, throttle deferral, translations and reader ACLs.
- Local 500-row Excel benchmark: prior implementation 3.032 seconds; optimized implementation 1.828 seconds (1.66x throughput, about 40% less time). Production performance remains unmeasured.
- Minimum observed invoice-request interval was 0.547 seconds; every tested one-second window had at most two starts. Verified a 120-second Retry-After suppressed further requests and left the UUID pending.
- All fixtures were rolled back; no live ETA or Telegram requests were made. Temporary tests and generated artifacts are excluded from the addon.

4e529760709c5310254e767728a889639ae74f27 - yahyazakaria22 - 2026-11-15
fix: close stale ETA detail progress entries

- Close the current detail callback's web progress entry when a partial batch ends, is deferred or raises an exception. Unfinished UUIDs remain queued for later callbacks, preventing stale progress cards from suggesting duplicate running jobs.
- Reuse the existing operation description and leave shared web_progress components, API pacing, retrieval ordering and overlap protection unchanged.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

Validation (2026-11-15):

- Targeted ETA module upgrade passed in eta_validation_20261115 with alternate ports and cron disabled.
- Tested real web.progress persistence for partial, deferred and failed batches. Each callback ended with a done progress entry and disappeared from active operations; all unfinished UUIDs stayed pending and the task lock released.
- Rolled back archive fixtures and removed only the test's transient progress rows. No external HTTP calls were made. No user-facing strings changed.

522e0b92d2657443712254e0fa0cb5cd1004d244 - yahyazakaria22 - 2026-11-15
feat: order ETA detail retrieval and prevent overlapping runs

- Retrieve eligible UUID details newest day first, with invoices before receipts for each day; only then continue to the previous day. Preserve issue-time order across interleaved directions and connections.
- Keep invoice and receipt scheduled jobs separate, coordinate their queue head, prioritize the invoice cron and trigger the next task after releasing the queue lock. Avoid duplicate pending trigger records.
- Guard the detail queue with a PostgreSQL transaction advisory lock on a dedicated cursor so scheduled/manual duplicate runs cannot overlap, even across progress commits. This bounded lock query does not modify business data and releases on failure or worker exit.
- Align pending-detail indexes with date/issue-time ordering while retaining bounded batches, pooled HTTP sessions, cached tokens, 0.6-second request pacing and persisted Retry-After cooldowns.
- Identify the operation in web progress descriptions with invoice/receipt type, sent/received direction and issue date. Maintain all four descriptions in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

Validation (2026-11-15):

- Targeted ETA module upgrade passed in eta_validation_20261115 with alternate ports and scheduled jobs disabled.
- Passed seven validation groups using actual PostgreSQL locks and mocked ETA HTTP: day/type order, interleaved issue-time order, inactive/future/retry-cooling exclusions, token reuse, request pacing, 429 deferral, deduplicated task handoff and priorities.
- Verified a second worker cannot acquire the detail lock after the main worker commits, duplicate entry points do not execute their batches, and locks release after deliberate exceptions. Verified handoff happens after releasing the lock.
- Minimum observed invoice-request interval was 0.593 seconds, with at most two starts in every tested one-second window. A 120-second Retry-After response persisted a longer cooldown and left the UUID pending without another HTTP call.
- All fixtures were rolled back; no live ETA or Telegram requests were made. Temporary tests are excluded from the addon.
- Progress descriptions: targeted module upgrade passed, exported the Odoo 19 POT, checked both PO catalogs with Babel, and verified all four English/Arabic runtime messages include the correct operation, direction and date. GNU msgfmt remains unavailable locally.

c8ccaadd9d324034dbad211878204ba892445550 - yahyazakaria22 - 2026-11-15
fix: recover missing ETA Telegram delivery days

- Generate and send each daily file when its own invoice/receipt direction has finished retrieval and UUID details are ready; unrelated failed streams no longer block the whole date.
- Save the next automatic Telegram scan date so older missing days are reached across cron time limits. Wrap at the configured start date and retry blocked dates on later sweeps.
- Preserve queued delivery requests after failed sends and clear them only after successful delivery.
- Log the specific date/category waiting for retrieval or UUID details, and translate the checkpoint label and revised manual-send validation in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

Validation (2026-11-15):

- Targeted ETA module upgrade passed in eta_validation_20261115 with alternate ports and cron disabled.
- Generated actual XLSX files with all Telegram HTTP calls mocked. Verified independent stream delivery, recovery of the 2026-11-04 example, missing-detail hold/recovery, no duplicate sends, retained failed requests, manual-send validation and resume after a forced time-budget interruption.
- Verified both Arabic catalogs with Babel and Arabic runtime field translation, plus denied reader writes to the delivery checkpoint. All fixtures were rolled back.
- The local abdin_replica19 database has no ETA archive tables, so the actual production delivery status for 2026-11-04 could not be inspected. No live ETA or Telegram requests were made.

6ab70466d834be981daec025b790784c08db457e - yahyazakaria22 - 2026-11-15
feat: optimize ETA retrieval and configure Telegram delivery start

- Restore invoice UUID detail retrieval and separate invoice/receipt discovery and detail fetching into four scheduled jobs. Preserve the existing invoice job XML IDs on upgrade.
- Select bounded 80-row detail batches, prioritize never-attempted rows, and index only pending detail rows instead of repeatedly scanning the completed archive.
- Reuse pooled HTTP connections and cache OAuth tokens until their advertised expiry, with a 60-second renewal margin and one refresh on a detail-request HTTP 401.
- Reserve independent invoice/receipt raw-request slots targeting 0.6 seconds apart across cron workers and duplicate connections using the same ERP/POS identity.
- Persist HTTP 429/503 cooldowns beyond Retry-After, including exhausted search retries; support numeric and HTTP-date headers and leave throttled or time-budget-deferred work queued.
- Reduce invoice search pacing from 2.1 to 0.6 seconds per call, preserve pagination validation and receipt date/result limits, and avoid rewriting unchanged search rows.
- Maintain English source labels and both Arabic catalogs for the split scheduled jobs and protected authentication/rate state fields.
- Expose Telegram Delivery Start Date in connection settings and apply it inclusively to automatic unsent-file delivery. Fall back to the archive start date when empty, retain the four-day automatic wait and preserve explicit manual delivery requests.

Files changed:

- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

Validation (2026-11-15):

- Installed and targeted-upgraded ab_tax_eta_archive in the isolated eta_validation_20261115 database with workers and scheduled jobs disabled and alternate ports 5069/5072.
- Passed 12 mocked behavioral/access check groups: stream isolation/idempotency, OAuth reuse, duplicate-identity pacing, per-endpoint reservations, cooldowns, Retry-After formats, final search throttles, 401 renewal, raw payload parsing, both detail cron flows, cron XML records, and denied reader access to credentials/caches.
- Passed Python/XML syntax and both PO catalog/message-format checks (266 messages each); exported the Odoo 19 POT and verified a scheduled action differs between en_US and ar_001 at runtime.
- GNU msgfmt was unavailable locally; Babel validated PO syntax and message formats instead.
- Follow-up checks passed for inclusive Telegram delivery dates, future dates, the empty-date fallback, sent-file deduplication and the existing four-day wait. Verified the new field is visible and translated in ar_001; both updated catalogs pass Babel checks.
- Measured 10 rate reservations across independent PostgreSQL transactions: minimum 0.594 seconds, mean 0.600667 seconds, maximum 0.609 seconds; every tested one-second window contained at most two starts. The first receipt reservation used its independent budget without waiting. ETA publishes a two-request/second cap for these APIs, implying 0.5-second spacing for evenly paced calls; this local timing test does not establish a live server acceptance threshold.
- No live ETA or Telegram requests were made. Production throughput remains unmeasured. Validation scripts and generated assets are excluded from the addon package.

SDK references:

- https://sdk.invoicing.eta.gov.eg/apigovernance/
- https://sdk.invoicing.eta.gov.eg/integrationpractices/
- https://sdk.invoicing.eta.gov.eg/api/01-login-as-taxpayer-system/
- https://sdk.invoicing.eta.gov.eg/einvoicingapi/08-get-document/
- https://sdk.invoicing.eta.gov.eg/ereceiptapi/04-get-receipt/

Recent relevant commits:

ec21df7dfae641390db809b989b940bb352ee7e0 - yahyazakaria22 - 2026-11-04
fix: pace ETA receipt raw requests using SDK rate limit

- Pace receipt raw requests at 0.6 seconds between starts.
- Keep the pacing checkpoint precise across cron callbacks.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

3ba879d79af61720c93cfe2c9ad65282beb5df97 - yahyazakaria22 - 2026-11-04
fix: fetch receipt UUID details only in 10000-row batches

- Pause invoice details while draining the receipt backlog.
- Select up to 10,000 eligible receipt UUIDs per batch.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

ecc63290b0368967294e6943c98ec89c1f8b2cac - yahyazakaria22 - 2026-11-04
fix: fetch ETA invoice details directly from raw

- Fetch invoice details directly from the raw endpoint.
- Remove the extra details request and parsing fallback.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d
