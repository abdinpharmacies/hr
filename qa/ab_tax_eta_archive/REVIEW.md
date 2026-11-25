# ETA archive review — 25 November 2026

Implemented version: **19.0.1.1.2**. Local source and running validation registry: **Odoo 19.0**.
Only the dedicated `eta_review_20261125` database was installed/upgraded. No live ETA,
Telegram, production archive, inventory, or external database writes were performed.
Tests live outside the production addon to keep its package runtime-only.

## Follow-up: Nov 22 sent receipts stuck at Details incomplete

The supplied file has no generated content yet. Its old Record Count is the exported-file
count, not the archived-receipt count. Generation waits for missing UUID details.

Confirmed queue causes: the detail selector chose one newest document type globally,
allowing newer invoice work to keep receipt jobs from fetching anything. Within a stream,
newest-first selection also delayed older dates. Manual actions did not wake scheduled
jobs outside cron context. Stopped slices left web_progress cards ongoing, so several
past slices could appear to be concurrent receipt workers.

Version 19.0.1.1.2 changes:

- Invoice and receipt queues run independently with one advisory lock per stream. Manual
  and scheduled receipt fetches share the receipt lock; API budgets still share credential
  owners and preserve the existing request pacing. Dates/connections rotate between slices.
- Fetch Missing Details targets the selected connection, issue date and direction for at
  most one 25-second slice. It can retry failed rows explicitly, while provider cooldowns
  continue to apply. It generates the file only when all required details are ready.
- Completed manual work wakes the relevant jobs. Throttled requests receive a future
  trigger after the provider cooldown; the current trigger does not suppress that retry.
- The file form/list reports Archived Documents, Details Ready, Details Pending and Detail
  Errors. Last Detail Error explains failed requests. Exported Rows remains the file count.
  Last batch row count, duration and rows/minute are observations of that batch, not a
  prediction of sustained production throughput. Scheduler enabled/last/next times include
  queued triggers and make disabled jobs visible.
- Background detail slices no longer emit interactive progress-card percentages. Queue
  counts and timestamps represent their progress; refresh the browser after deploying to
  clear old cached cards. Shared web_progress code/templates are unchanged.

Validation: 48 integration tests passed. A real `method_direct_trigger()` receipt-detail
job processed a Nov-22-style older receipt despite newer pending invoices, then the actual
file job generated a nonempty workbook. A second detail run did not refetch completed data.
A provider 429 scheduled the next attempt after its 120-second Retry-After. HTTP is mocked;
these results do not confirm production credentials, provider responses or throughput.
The standalone `detail_cron_check.py` reproduces that committed scheduler path.

Deployment: stop/restart all Odoo workers around the targeted module upgrade because lock
ownership and Python queue logic changed. Pulling code alone does not reload Python in
running workers. Open the Nov 22 Receipts sent record and use Fetch Missing Details; inspect
pending/error counts and Last Detail Error. If Detail Job Enabled is false, enable the
existing ETA: Fetch Receipt UUID Details job in Scheduled Actions. If enabled but its next
run remains overdue without new batches, inspect the production cron workers, database
filter and server logs; this coding environment cannot verify those server settings.

## Follow-up: package 205882 HTTP 400 and Done files without data

The supplied correlation ID does not identify ETA's reason for the 400. No live response
body or affected workbook/date was available. The following local faults were confirmed
and repaired; successful production recovery still requires retrying the affected operation.

- The HTTP wrapper accepted `raw_response=True` but never returned a raw response. Successful
  ZIP downloads and empty 204 responses went through JSON parsing. It now returns the stream,
  and binary downloads explicitly request `application/octet-stream`, including after refresh.
- Flat HTTP error codes/targets were discarded; nested errors were reduced to code alone.
  Safe codes, parameter targets and correlation IDs now remain available without response bodies.
- Package readiness is checked through the documented, paginated
  [request-status API](https://sdk.invoicing.eta.gov.eg/ereceiptapi/12-get-package-requests/).
  Each status page is resumable. Preparing requests wait; failed/missing requests show explicit
  errors and retain their ID. Confirmed expired requests retain history and can renew at most twice.
  A download 400/404 rechecks status; a package still reported available preserves the original error.
- Ready file dates previously waited behind `file_scan_date`. Retrieval/detail completion now
  nominates the affected issue dates, and existing waiting/unverified files are considered first.
  Failed builds retry after five minutes; blocked prerequisites are revisited hourly or immediately
  when new retrieval/details nominate them. The ordinary historical sweep remains available.
- Cache reuse trusted metadata, without checking actual workbook rows. Existing header-only or
  invalid files can therefore appear ready. Reuse/delivery now checks the actual document-ID rows
  and content digest; new files are checked before being marked generated. Valid sent files are
  verified without changing bytes or adding a revision. A repaired sent file becomes a correction.
- Daily Files now offers **Generate Files** for a targeted retry and **File Rows** after content
  verification. An archived count of zero still means no records for that issue date; retrieval
  Done alone is not evidence that there should be rows in every issue-date file.

Validation: **38 integration tests passed in 4.951 seconds** (excluding Odoo startup).
Regression coverage includes real HTTP-wrapper ZIP/204 handling, package status
pagination and failures, expiry renewal limits, priority generation, actual XLSX UUID/VAT values,
header-only/styled-blank-row repair without a new data event, valid sent-file reuse, and Arabic
runtime labels. The earlier tests mocked the download helper and missed the raw-response bug.
After deployment, upgrade only `ab_tax_eta_archive`, restart Odoo, retry the affected retrieval,
and use Generate Files for the affected date. Inspect package Remote Status/Error and File Rows.
No existing package IDs, archived documents or sent files need to be deleted.

## Findings and changes

| Issue | Observed cause | Implementation |
|---|---|---|
| Premature Done | Receipt retry and detail-slice progress explicitly reached 100% even when work remained. Package rows became Done after download and during partial imports. Invoice pages were buffered until completion. | Removed forced completion; persistent Pending / Partial / Error / Done retrieval states; page writes and their checkpoint share a savepoint; completion timestamp only after the entire eligible day finishes. Package states distinguish ready, importing, and fully imported. UUID details and file readiness remain separate from summary retrieval. |
| Current-day retrieval | Cron created today's operations and retrieval explicitly permitted incremental current-day work. No safety delay existed. | Per-connection Safety Delay Hours defaults to 12. UTC cutoff is `min(Cairo midnight today, now UTC - delay)`. Manual and scheduled retrieval share this check. A partially eligible yesterday remains Partial and resumes when the cutoff advances. File readiness also checks the complete day against this cutoff. |
| Slow retrieval | Receipt processing probed every hour before paging; invoice search restarted/split after 20 pages; page buffering and whole-attempt rollback repeated successful work. Receipt submission/issue filtering had diverged from historical package validation. | Fetch one page per step, save the cursor/page and split-window queue, batch-create new rows, avoid unchanged summary writes, and remove redundant receipt probes and the artificial invoice page cap. Add `(config_id, direction, received_at)` indexes. Retain existing pending-detail indexes and token cache; reuse sessions for searches, authentication and package downloads. Receipt retrieval consistently uses submission dates; exports retain issue dates, including late submissions. |
| Frequent/overlapping jobs | All six jobs had one-minute defaults. Existing task locks protected details/generation/delivery, but retrieval depended on transaction row locks and lacked a queue-wide guard. | Five-minute adjustable defaults under `noupdate`; retrieval queue and operation advisory locks plus existing row locks; retain other task locks. A separate cursor owns each advisory lock across business commits. Search calls sharing credentials also share an API lock. No persistent stale-lock flag requires clearing after connection loss. |
| Receipts older than 29 days | Historical package support existed but was disabled, so older dates were silently skipped. Existing package splitting left subsecond gaps, and `dateTo` was extended almost a second beyond its saved boundary. | Enable historical packages; requests are split into daily operations and adaptively split again at the result limit. Recent receipt pages checkpoint independently; historical package IDs, windows, payloads and 200-row import offsets persist. Correct contiguous boundaries, complete fractional-second upper bounds, and reject invalid/out-of-window data. Polling 204 waits five minutes; long Retry-After values defer the operation. |
| Missing files | The latest code already iterated categories independently; there was no universal 'one file means day complete' shortcut to remove. However, empty/waiting/failed cases were only skipped or logged, and premature retrieval/progress indications made readiness misleading. | Persist each category independently as Retrieval incomplete, Details incomplete, No records, File generation failed, or File generated. Keep generation scanning every date/category; retry missing or failed files; reuse unchanged files; retain sent revisions. A day-completion predicate requires all four categories to be current files or confirmed empty. |
| Missing icon | No module application icon or menu registration existed. | Added a 256px document/shield icon in `static/description/icon.png` and registered the root menu's Odoo `web_icon`. |

`error_message` shows the current problem; `last_error` retains the last diagnostic after
recovery. Logs identify connection, type, direction, date/window, page, counts, duration
and exception type without logging tokens or tax payloads. HTTP diagnostics retain status,
endpoint, error code and correlation ID rather than copying server response bodies.

Existing UUID uniqueness constraints, documents, package payloads, sent files and revisions
are retained. A failed page rolls back with its checkpoint; preceding committed pages survive.
Old receipt checkpoints explicitly based on submission dates can resume. Old **issue-date**
checkpoints and segments remain saved, but their day is reconciled from the start because
they cannot safely represent the new submission-date coverage. Upserts make that replay safe.

## Official API contracts checked

- [Invoice search](https://sdk.invoicing.eta.gov.eg/einvoicingapi/16-search-documents/):
  continuation tokens, `EndofResultSet`, default 30-day filter difference, no overall document
  count limit. This endpoint's own page says one request every two seconds; the implementation
  conservatively spaces search calls by 2.1 seconds despite the less restrictive governance table.
- [Receipt search](https://sdk.invoicing.eta.gov.eg/ereceiptapi/07-search-receipts/): separate
  issue/submission filters, numeric pages and total counts, configurable page size, default
  one-month recent availability and configurable 3,000-result cap. Splitting a date range alone
  does not recover history outside that availability period.
- [Receipt package request](https://sdk.invoicing.eta.gov.eg/ereceiptapi/11-request-receipt-package/)
  and [download](https://sdk.invoicing.eta.gov.eg/ereceiptapi/13-get-receipt-package/): asynchronous
  historical extraction, adaptive narrowing when the result limit is exceeded, full JSON ZIP
  import and HTTP 204 while preparation is incomplete.
- [Raw receipts](https://sdk.invoicing.eta.gov.eg/ereceiptapi/04-get-receipt/) define the full
  package structure. [Rate-limit guidance](https://sdk.invoicing.eta.gov.eg/apigovernance/)
  documents 429, 503 and Retry-After. Retrieval retries connection errors and transient
  500/502/503/504 responses with bounded backoff/time budgets and refreshes authentication
  once on 401. No speculative parallel API fetching was introduced.

Intervals are half-open internally. Checkpoints split on millisecond boundaries; API upper
bounds include the entire last millisecond using seven fractional digits, stopping one ETA
timestamp tick before the next boundary. New stored timestamps retain Python/PostgreSQL
microseconds, while raw JSON preserves the original timestamp text. Cairo day bounds are
localized separately to handle DST days of different lengths.

## Initial review validation and performance

- Clean install and targeted `-u ab_tax_eta_archive` upgrade passed in the isolated Odoo 19 DB.
- **27 integration tests passed in 4.187 seconds** (excluding Odoo startup). The suite covers page completion, partial rollback/resume, duplicate detection,
  25 invoice pages without restart, 90-day receipt planning, package split/import/polling,
  cutoff and DST boundaries, same-operation and shared-credential locks, page-size fallback,
  retries, late submissions, independent file regeneration/reuse, and Arabic runtime strings.
- A real `ir.cron.method_direct_trigger()` run with mocked HTTP confirmed that another DB
  transaction can see page one's committed rows/checkpoint after page two fails, followed by
  successful resumption. The script deactivates its test connection when finished.
- An upgrade snapshot comparison passed for document IDs/raw/detail content, a Partial
  checkpoint, error history, a sent file, and a customized seven-minute schedule. This is a
  populated test fixture check, not a production database upgrade rehearsal.
- Odoo-exported POT used to append 40 missing Arabic entries to both catalogs and merge
  needed references without replacing unrelated translations. Babel format checks passed;
  runtime `ar_001` action and new configuration-field labels differed from English.
- Sparse/empty receipt day: prior source performs **24 hourly search probes**; the new mocked
  integration run performs **1 request**, a **95.8% reduction**. A 25-page invoice fixture used
  exactly 25 requests, with no replay at page 20. These are request-count comparisons, not
  measured production throughput or network latency. No production tax-detail speedup is claimed.

## Modified files

- `ab_tax_eta_archive/models/eta_retrieval.py` (new): resumable retrieval, states, scheduling and operation locks.
- `ab_tax_eta_archive/models/eta_policy.py` (new): Cairo cutoff and interval/boundary helpers.
- `ab_tax_eta_archive/models/eta_sync.py`: retained core models, parsing and HTTP helpers; removed obsolete whole-run retrieval paths; shared search locking and retries.
- `ab_tax_eta_archive/models/eta_package.py`: historical package lifecycle, boundaries, download and polling.
- `ab_tax_eta_archive/models/eta_config.py`: configurable safety delay and validation.
- `ab_tax_eta_archive/models/eta_document.py`: submission-window indexes and timestamp precision.
- `ab_tax_eta_archive/models/eta_export.py`: persistent category outcomes, source completeness and retry handling.
- `ab_tax_eta_archive/models/eta_dashboard.py`: yesterday default and partial/error/file reporting.
- `ab_tax_eta_archive/models/__init__.py`: retrieval extension import.
- `ab_tax_eta_archive/views/eta_views.xml`: configuration, progress/file states and icon registration.
- `ab_tax_eta_archive/static/src/js/eta_dashboard.js`, `static/src/xml/eta_dashboard.xml`: Partial counter.
- `ab_tax_eta_archive/static/description/icon.png` (new): application icon.
- `ab_tax_eta_archive/data/cron.xml`: adjustable five-minute defaults.
- `ab_tax_eta_archive/i18n/ar.po`, `i18n/ar_001.po`: Arabic additions and Odoo references.
- `ab_tax_eta_archive/__manifest__.py`: version 19.0.1.1.2.
- `ab_tax_eta_archive/changelog.d`: current changes and corrected recent-commit attribution.
- `qa/ab_tax_eta_archive/`: standalone test/upgrade/cron/translation helpers and this report;
  generated logs, POT, snapshots and filestore are ignored.

## Deployment

1. Take the normal database backup and deploy the addon code. Restart Odoo to load the Python changes.
2. Run only the targeted upgrade, with scheduled workers disabled during it:

   ```sh
   odoo-bin -c <config> -d <database> -u ab_tax_eta_archive --stop-after-init --max-cron-threads=0
   ```

3. Verify each ETA connection's **Safety Delay Hours = 12** (or the agreed delay). Historical
   packages require the taxpayer ERP/invoice credentials even when recent receipts use POS credentials.
4. Set the six existing ETA Scheduled Actions to **5 minutes**, or agreed intervals. Existing
   intervals are intentionally preserved by `noupdate`; upgrading does not forcibly overwrite
   an operator's settings. Fresh installs receive five-minute defaults.
5. Resume scheduled workers. Partial operations resume automatically; failed operations are
   eligible after the retry delay. A manual Retry advances one bounded page/package step.
   Inspect Partial plus its error/checkpoint, not only an ended cron callback/progress card.
6. Let file generation sweep existing dates. Waiting/empty/error entries have no fake downloadable
   file. Existing sent files are retained; changed source data may produce a numbered revision.

No hooks, migrations, deletion, direct business-data SQL, or base-module upgrade are required.

## Reproduce local checks

Use a normal working Odoo Python environment. `odoo_runner.py` is a local Windows fallback
that uses the installed dependencies without modifying the broken virtualenv launcher.

```powershell
"exec(compile(open('qa/ab_tax_eta_archive/test_eta_archive.py', encoding='utf-8').read(), 'qa/ab_tax_eta_archive/test_eta_archive.py', 'exec'))" |
  <python> qa/ab_tax_eta_archive/odoo_runner.py <odoo-source> shell `
  -c <config> -d eta_review_20261125 --no-http --max-cron-threads=0 --data-dir=<isolated-data-dir>
```

Use the same shell loader for `cron_check.py`. For the upgrade snapshot, run `upgrade_check.py`
with `ETA_QA_PHASE=prepare`, perform the targeted upgrade, then run it with `ETA_QA_PHASE=check`.
Those two helpers explicitly refuse other database names; the main suite rolls back fixtures.

## Remaining verification

- **Live ETA was not called.** In preproduction, reconcile a 60–90 day range and a busy day
  exceeding 3,000 receipts against the ETA portal by UUID, including receipts issued and submitted
  on different days. Verify package date filters use the expected submission-date basis: the
  package documentation labels UTC dates but does not explicitly name their basis. Unexpected
  package rows are rejected rather than silently treated as a completed day.
- Confirm both APIs accept the seven-digit inclusive upper bounds and test documents exactly
  around midnight and an adaptive split. Compare IDs on both sides of each boundary.
- Kill a dedicated preproduction retrieval worker after a committed page, restart it, and check
  checkpoint continuation and advisory-lock release. Local checks exercised lock contention,
  exception release and real cron commits, not an OS-level worker kill or multi-host failover.
- Measure live records/minute, HTTP time, DB query time, 429 frequency and file build time before
  tuning intervals or page sizes. Large XLSX construction remains an indivisible per-category
  step; a single very large workbook can exceed the soft slice deadline.
- GNU `msgfmt` is not installed locally. Run `msgfmt --check-format` against both PO files in
  CI/deployment. Babel checks and actual Odoo translation import/runtime verification passed.
- An expired invoice continuation token is retained as an explicit error/checkpoint. If ETA
  invalidates a persisted token, reconcile that one daily window again with a manager-controlled
  checkpoint reset; automatic interpretation of undocumented token-expiry errors is not implemented.
- The 29-day recent-search routing threshold remains conservative and local; ETA can configure
  its actual retention and result/page limits. Confirm those settings with the taxpayer account.
