85c52ad8 — yahyazakaria22 — 2026-10-24
feat: add ETA tax archive and issue-date reports

- Archive sent and received ETA invoices and receipts with retryable daily retrievals.
- Build issue-date Excel files, deliver eligible files to Telegram, and preserve numbered corrections.
- Add ETA settings, access groups, scheduled jobs, and Arabic translations.

Files changed:

- ab_tax_eta_archive/__init__.py
- ab_tax_eta_archive/__manifest__.py
- ab_tax_eta_archive/models/__init__.py
- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_sync.py

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/security/security_groups.xml
- ab_tax_eta_archive/security/ir.model.access.csv
- ab_tax_eta_archive/views/eta_views.xml

- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

39ff9b4d — yahyazakaria22 — 2026-10-24
feat: add ETA archive OWL dashboard

- Add an OWL dashboard with issue-date document cards and chart, submission-day retrieval health, file delivery counts, and a prominent warning for failed streams.
- Add date and connection filters, latest successful retrieval time, and navigation to the matching archive lists.
- Add a reader-guarded ORM summary method, module-scoped backend assets, and Arabic translations.

Files changed:

- ab_tax_eta_archive/__manifest__.py
- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/__init__.py
- ab_tax_eta_archive/models/eta_dashboard.py
- ab_tax_eta_archive/static/src/js/eta_dashboard.js
- ab_tax_eta_archive/static/src/xml/eta_dashboard.xml
- ab_tax_eta_archive/static/src/scss/eta_dashboard.scss
- ab_tax_eta_archive/views/eta_views.xml

ffada7d4 — yahyazakaria22 — 2026-10-24
fix: continue ETA backfill and support taxpayer receipt access

- Continue the daily backfill after a failed retrieval, retry incomplete days, and progress pending receipt packages.
- Add taxpayer ERP receipt authentication for authorized POS devices while retaining optional POS-device authentication.
- Store receipt POS serials, include them in Excel files, and show per-POS receipt coverage and not-started days on the dashboard.
- Clarify missing invoice and receipt credentials in retrieval errors and update both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_dashboard.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/static/src/js/eta_dashboard.js
- ab_tax_eta_archive/static/src/scss/eta_dashboard.scss
- ab_tax_eta_archive/static/src/xml/eta_dashboard.xml
- ab_tax_eta_archive/views/eta_views.xml

38ed2546 — yahyazakaria22 — 2026-10-25
fix: avoid mixed-unit Sass function in ETA dashboard

- Fix dashboard stylesheet compilation by replacing a mixed-unit Sass min() call with CSS width and max-width properties.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/static/src/scss/eta_dashboard.scss

5f804a0a — yahyazakaria22 — 2026-10-25
fix: share ERP authentication and recover receipt search 404

- Use the taxpayer ERP invoice client credentials and Basic authentication for both invoice and receipt retrievals.
- Retry a receipt day through ETA receipt packages when the search route returns HTTP 404.
- Show the failed ETA method and endpoint without exposing credentials or query values.
- Clarify POS-only credentials in the connection form and update both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/views/eta_views.xml

1837dcc2 — yahyazakaria22 — 2026-10-25
fix: keep recent ETA receipts on search API

- Keep recent receipt retrieval on ETA Search Receipts; use receipt packages only for dates outside the search window.
- Include ETA error code, message, target, and correlation ID in retrieval errors when returned.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

4e3caac7 — yahyazakaria22 — 2026-10-25
fix: bound ETA pagination and read receipts to empty page

- Page receipt searches until an empty page with a bounded PageNo and verify collected UUIDs against ETA's reported total.
- Retain 100 receipts per page, split windows at the 3,000-result limit, and add a safety cap for invoice continuation-token pages.
- Wait between pages to respect ETA's published request rate limit.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/models/eta_sync.py

394a20f2 — yahyazakaria22 — 2026-10-25
fix: request 1000 ETA receipts per search page

- Increase receipt search page size from 100 to 1,000 so each request retrieves more receipts before advancing to the next page.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

2fb75c51 — yahyazakaria22 — 2026-10-25
fix: use ETA receipt page size and page limit

- Set receipt search to PageSize 10 and PageNo up to 100, splitting result windows at 1,000 receipts.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

37f97a32 — yahyazakaria22 — 2026-10-25
fix: honor ETA 3000 receipt search result cap

- Set receipt search to PageSize 10 and allow up to 300 pages, splitting date ranges at 3,000 matches.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

57e97808 — yahyazakaria22 — 2026-10-25
fix: include ETA response body in retrieval errors

- Include up to 1,000 characters of ETA's raw error response when its standard error fields are absent.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

2d3b04f2 — yahyazakaria22 — 2026-10-25
fix: mark ETA no-result receipt searches complete

- Treat ETA's explicit 404 NotFound/NoResult search response as a successful empty receipt result; preserve other 404s as errors.

Files changed:

- ab_tax_eta_archive/changelog.d
- ab_tax_eta_archive/models/eta_sync.py

05e5d146 — yahyazakaria22 — 2026-11-01
fix: handle large ETA archive retrievals

- Fix the dashboard summary query to group archived documents by issue day in Odoo 19.
- Split oversized receipt and invoice searches into bounded date windows, including ETA limit responses.
- Import verified pages in batches to avoid holding a full day of documents in memory.
- Generate daily Excel files with streaming worksheets and a stable streaming digest.
- Recognize nested ETA limit and no-result responses while preserving count and UUID checks.

Files changed:

- ab_tax_eta_archive/models/eta_dashboard.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_sync.py

16030027 — yahyazakaria22 — 2026-11-01
fix: resume ETA receipt retrieval in ten-minute windows

- Retrieve recent ETA receipts in resumable 10-minute intervals and retain completed intervals after a later retry fails.
- Commit scheduled retrieval progress after each interval and run the sync job every minute.
- Resume pending backfill days before opening another day, while retrying failed days at most hourly.
- Check completed overlap days once daily to keep the faster schedule focused on unfinished work.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/data/cron.xml

0744699d — yahyazakaria22 — 2026-11-01
fix: split oversized ETA receipt packages

- Split oversized receipt package requests when ETA returns its observed HTTP 400 ValidationError with a document-count limit.
- Continue fetching the next receipt interval or package window in the same cron run while committing each completed step.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py

c287b4ad — yahyazakaria22 — 2026-11-01
fix: fetch ETA receipts through search

- Fetch receipt days through resumable 10-minute Search Receipts windows instead of creating or downloading ETA receipt packages.
- Keep existing package records for audit while removing package request and download calls.
- Report historical receipt days as incomplete when ETA's recent-only search cannot verify full coverage.
- Translate the historical completeness warning in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po

158b6979 — yahyazakaria22 — 2026-11-02
fix: make ETA dashboard scroll within action

- Constrain the OWL dashboard to the available action height so its existing overflow container scrolls through all sections.

Files changed:

- ab_tax_eta_archive/static/src/scss/eta_dashboard.scss

ae427ccf — yahyazakaria22 — 2026-11-02
fix: align ETA receipt cron with issued-time search

- Search receipt issue-time windows as the working VB.NET harvester does, with stable issue-time sorting and daily counts.
- Restart legacy received-time checkpoints from the start of their day while preserving already imported receipt records.
- Reuse the ETA token across receipt windows in one cron run and accept documented or nested receipt search response layouts.
- Keep successful retrievals committed when daily Excel generation fails, and log the export error for repair.
- Recognize ETA's No data found response without treating unrelated errors as empty results.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py

287f1011 — yahyazakaria22 — 2026-11-02
fix: prevent overlapping ETA receipt imports

- Search receipts in five-minute windows so each cron step and manual retry handles less data.
- Lock each daily retrieval to prevent overlapping cron and manual runs from importing the same receipts together.
- Recover from a receipt UUID insert race by retrying the affected batch per receipt and updating records inserted by another run.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py

bf45df90 — yahyazakaria22 — 2026-11-02
fix: list every configured ETA retrieval day

- Create retrieval rows for every configured day and all four streams before processing, including a pending row for the current day.
- Batch row creation so a long backfill can resume safely across cron calls.
- Process the oldest eligible unfinished day after the priority dates instead of depending on list order.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py

3b31488e — yahyazakaria22 — 2026-11-02
fix: prioritize ETA invoices and pace search requests

- Process eligible invoice retrievals before receipt retrievals and keep receipts queued while invoice work remains.
- Pace each ETA invoice search request by 2.1 seconds and each receipt search request by 0.6 seconds, including across pages and date windows.
- Wait beyond ETA's Retry-After value when a request is throttled.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py

1fcb6092 — yahyazakaria22 — 2026-11-02
feat: send completed ETA daily files to Telegram manually

- Create or refresh daily Excel files only after all four retrieval streams for their issue day are complete.
- Add a manager-only Send to Telegram button for unsent daily files in list and form views.
- Refresh an unsent file before manual delivery and lock delivery to avoid sending it twice.
- Translate the incomplete-day warning in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po

9d6dd100 — yahyazakaria22 — 2026-11-02
fix: resume ETA receipt retrieval alongside invoice backfill

- Give received and sent receipt retrievals scheduled time even while invoice backfill remains unfinished.
- Limit receipt work per cron attempt so one busy day does not occupy the entire run.
- Complete a recent received-receipt day with zero items when ETA confirms that the full day has no results.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

bc77be91 — yahyazakaria22 — 2026-11-02
fix: jump to first ETA receipt on manual retry

- Make Retry locate the earliest remaining receipt issue time before fetching its five-minute window.
- Split oversized ETA searches while locating the first receipt, and finish a past day only after ETA confirms it is empty.
- Keep the current Cairo day pending when its receipt search is empty.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

e686ae65 — yahyazakaria22 — 2026-11-02
fix: retrieve historical ETA receipts through packages

- Retrieve historical sent and received receipts through ETA receipt packages instead of the recent-only search API.
- Resume package requests, split oversized windows, and download completed JSON packages on Retry or cron.
- Preserve recent issued-time searches and count historical package results by received time.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

99dbbde7 — yahyazakaria22 — 2026-11-02
fix: accept ETA empty receipt package response

- Treat ETA's explicit InvalidInput "criteria does not return any results" package response as an empty historical interval.
- Keep other HTTP 400 package request errors visible for correction.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

2259c86c — yahyazakaria22 — 2026-11-03
fix: adapt ETA receipt search windows to result volume

- Replace fixed five-minute recent receipt windows with count-based time splitting, following the Visual Basic harvester.
- Request up to 1,000 receipts per page with fallback for ETA page-size rejections and retain a 300-page safety limit.
- Preserve receipt checkpoints and existing daily counts when the remaining period is empty.
- Reject a changed-to-empty result after a nonempty probe so incomplete receipt ranges can be retried.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

0b24a4ff — yahyazakaria22 — 2026-11-03
fix: checkpoint ETA receipts by hour and skip today

- Process recent receipt retrievals one Cairo-day hour at a time and split only oversized hours into verified subranges.
- Save the next UTC receipt checkpoint after each completed hour or subrange so cron resumes from the last complete interval.
- Keep today's receipt and invoice retrievals pending without calling ETA, and clear today's partial receipt checkpoint for a full scan tomorrow.
- Limit manual recent-receipt Retry to one committed interval while allowing cron to continue through several intervals.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

5d64455c — yahyazakaria22 — 2026-11-03
fix: refresh ETA Excel files after retrieval coverage completes

- Create or refresh daily Excel files only after all configured retrieval days from their issue day through yesterday are complete.
- Reconcile existing early-created files and create missing completed-day files before Telegram delivery.
- Track the submission-day coverage checked for each file without clearing it during manual Telegram sends.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

6ef17c30 — yahyazakaria22 — 2026-11-03
fix: show ETA receipt retrieval segments and continue cron

- Report eligible unfinished ETA retrievals to Odoo after each cron pass so the scheduler continues while time remains.
- Count only actual state, count, checkpoint, or package progress; pause until the next scheduled run when ETA has no new package data.
- Show completed and failed receipt time segments on each Retrieval, including counts, last receipt, and failure reason.
- Show the next receipt checkpoint so Retry resumes the remaining part of the day.
- Preserve verified empty subranges in each completed segment's displayed coverage.
- Retain completed receipt intervals and the existing one-hour error retry delay.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/security/ir.model.access.csv
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

c5e5d1c6 — yahyazakaria22 — 2026-11-03
feat: report ETA receipt loop progress

- Report ETA receipt window, page, and package loop progress through web_progress when that addon is installed.
- Show start and completion of a manual receipt Retry through web_progress.
- Preserve the existing retrieval and checkpoint behavior when web_progress is unavailable.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

27be06f3 — yahyazakaria22 — 2026-11-03
fix: avoid shadowing ETA translation in receipt loop

- Fix the cron and Retry crash caused by a receipt loop variable shadowing Odoo's translation function.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

910ff863 — yahyazakaria22 — 2026-11-03
feat: organize ETA streams and transactions by day

- Process each eligible ETA day across received invoices, sent invoices, sent receipts, and received receipts before moving to another backlog day.
- Add four transaction menus filtered by direction and grouped by issue date, with Retrievals grouped by day.
- Show the same category order and names in the dashboard and daily file labels.
- Sort invoice and receipt lists by issue day.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/static/src/js/eta_dashboard.js
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

bae05edc — yahyazakaria22 — 2026-11-03
fix: disable ETA receipt package retrieval

- Stop creating and downloading ETA receipt packages; use receipt search with hourly checkpoints for eligible days.
- Leave older receipt days in Error with an explicit search coverage message instead of treating unverified days as complete.
- Hide the old package list while preserving package records already stored in production.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

6d067c0d — yahyazakaria22 — 2026-11-03
fix: expose Telegram delivery errors and find group chat IDs

- Show Telegram's HTTP error detail and safely retry short rate limits during daily file delivery.
- Reject invite links, positive IDs, empty files, invalid files, and files above Telegram's 50 MB upload limit with specific messages.
- Add a manager-only action to read candidate group chat IDs from the configured bot's recent updates without exposing its token.

Files changed:

- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d
4b0843b1 — yahyazakaria22 — 2026-11-03
feat: match ETA daily exports to sample workbooks

- Match the ETA sample workbook sheet names, Arabic headers, column order, widths, borders, dates, and invoice share links for four daily export categories.
- Retrieve and cache the UUID details required for tax, discount, address, POS, buyer, and signature columns in rate-limited, resumable batches.
- Keep each file pending until its transaction details are complete, show per-document detail errors, and run export enrichment every minute without delaying retrieval.
- Add Arabic translations for the new detail status and export messages.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

a8347b5f — yahyazakaria22 — 2026-11-03
fix: handle empty ETA invoice tax items

- Allow invoices with no taxable items on a line to finish UUID enrichment and export.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

c7bee30f — yahyazakaria22 — 2026-11-03
fix: keep expired ETA receipt days pending

- Keep receipt retrievals older than the conservative ETA search window Pending with a clear reason, and stop cron from retrying those unsearchable days every hour.
- Preserve previously archived receipt rows and completed retrievals without claiming that an older day is complete.
- Let completed searchable days prepare their Excel files independently of older incomplete days, prioritizing the delivery day and yesterday.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

76513fba — yahyazakaria22 — 2026-11-03
fix: rebuild unsent ETA files from four-day cutoff

- Rebuild unsent daily files in descending issue-date order from four days ago through the configured archive start date, only after all required retrievals and UUID details are complete.
- Avoid creating any of the four files for a day until every unsent category has its detail data, and keep delivered file revisions unchanged.
- Mark the current workbook format so existing unsent files are regenerated once even when their source digest matches.
- Continue to older eligible days when one day's detail enrichment is still pending, and keep Telegram delivery subject to its configured start date.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

f8d84d7d — yahyazakaria22 — 2026-11-03
fix: queue ETA Telegram sends outside browser requests

- Queue the Send to Telegram action for cron delivery instead of rebuilding large workbooks and uploading them inside an Odoo browser request.
- Enforce the four-day delivery delay for manual sends and show whether a file is queued.
- Record the generated workbook size and show a specific error when it exceeds Telegram's upload limit.
- Add Arabic translations for the new delivery status, size, and delay messages.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

c88cecdd — yahyazakaria22 — 2026-11-03
fix: revise sent empty ETA files when rows arrive

- Detect delivered daily files whose saved row count differs from the currently archived transactions.
- Create an unsent corrected revision after the day's details finish, preserving the original delivered file.
- Deliver a corrected revision even if its original file predates the configured Telegram start date.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

84e699fd — yahyazakaria22 — 2026-11-03
fix: allow manual ETA sends before auto cutoff

- Allow the manual Send to Telegram action for any previous day whose required retrievals are complete, while automatic delivery retains its four-day delay.
- Process manually queued recent files through the export cron after their UUID details and workbook are ready.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

d2cfabcc — yahyazakaria22 — 2026-11-03
fix: deliver all eligible unsent ETA daily files

- Let the export cron scan every eligible day even when yesterday's completed retrievals have not rerun today.
- Automatically create and send every unsent file dated at least four days before today, including days before the former Telegram start date, once required retrievals and document details are complete.
- Remove the unused Telegram start date from the connection form.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/changelog.d

4b9e00a5 — yahyazakaria22 — 2026-11-03
fix: resume ETA export details and deliver ready files

- Commit each fetched UUID detail so a long ETA export cron run can resume after its time budget instead of losing the batch.
- Prepare and deliver each completed category independently once its retrievals and UUID details are complete, while leaving unfinished categories pending.
- Bound each cron pass, persist each created workbook and Telegram result, and avoid sending an older file while its category is being refreshed.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

297403d0 — yahyazakaria22 — 2026-11-04
feat: fetch ETA UUID details in separate cron

- Add a dedicated minute-by-minute ETA UUID detail cron that fetches saved invoice and receipt details for past issue dates, committing each request so it resumes safely.
- Make file generation read saved UUID details only; the delivery cron no longer makes ETA detail HTTP requests.
- Show UUID detail readiness, last attempt, and error on invoice and receipt lists, with manager filters for missing details and errors.
- Translate the new scheduled job and status labels in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

829c2e91 — yahyazakaria22 — 2026-11-04
fix: create ETA files per completed day

- Treat each issue day independently: its four retrieval streams must be Done before building its daily XLSX files.
- Create files for completed recent days without automatic Telegram delivery; automatically send every ready unsent day on or before the Cairo four-day cutoff.
- Record the verified day on the file and rename the delivery scheduled action to clarify that the delay applies only to automatic sending.
- Translate the new scheduled action name in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/data/cron.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

22ae74fc — yahyazakaria22 — 2026-11-04
fix: block empty ETA files and show UUID coverage

- Prevent creation and Telegram delivery of headers-only daily XLSX files when the issue-day category has zero saved transactions.
- Show issue-day saved row counts and UUID detail ready/pending counts beside each retrieval stream, so an idle detail cron can be distinguished from missing source rows.
- Show VAT (T1), UUID detail state, last attempt, and error directly in invoice and receipt lists.
- Hide Send on existing empty files and translate the new diagnostics in both Arabic catalogs.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d

9926e630 — yahyazakaria22 — 2026-11-04
fix: show ETA UUID coverage and auth failures

- Fix the Odoo 19 Retrievals coverage view by grouping the report date at day granularity.
- Record UUID detail authentication failures on affected transactions with attempt time, so the detail job shows Error instead of silently leaving every row Pending.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

e1991eaa — yahyazakaria22 — 2026-11-04
fix: rotate ETA UUID detail retrieval across connections

- Select pending UUID details directly from saved invoice and receipt rows, including rows older than a connection's current start date, and rotate active connections each minute so later connections get a turn.
- Keep automatic delivery days first, rotate the four transaction categories, and fetch no current-day details.
- Include empty detail text and pending rows with no recorded error in retries; keep file creation blocked until every row in its category has usable detail data.
- Align Retrievals ready counts with the same nonempty detail rule.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/changelog.d

57fd26c4 — yahyazakaria22 — 2026-11-04
fix: fetch ETA UUID details in newest-first batches

- Start UUID detail retrieval with today's newest eligible issue day, then move backward through older days.
- Rotate ETA connection and transaction streams when they share the newest day, and select up to 10,000 pending UUIDs for the chosen stream.
- Continue the selected batch across scheduled runs within the cron time limit, while retaining the one-hour cooldown for failed UUID requests.
- Log selected, attempted, ready, and failed detail counts for each batch instead of reporting a misleading small progress bar.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

c1511bc3 — yahyazakaria22 — 2026-11-04
fix: start ETA UUID batches without scanning every stream

- Find the newest eligible issue day with one lookup per document model, reducing selection work before the detail request starts.
- Use issue-day ordering for selection and indexed row IDs within the selected 10,000-row batch.
- Log whether active connections have pending rows, whether any are dated through today, and when selection or batch search consumes the cron time budget.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

2466e011 — yahyazakaria22 — 2026-11-04
fix: validate ETA UUID raw response shapes

- Accept ETA invoice and receipt details from a validated wrapped object, nested result object, or direct document body; parse JSON document text when returned.
- Reject responses without the required document structure instead of marking incomplete data as ready.
- Log response key names and body type once per failed batch to diagnose ETA payload variations without recording document values.
- Stop reporting the next cron loop's exhausted time budget as a slow selection query.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

a22e2f90 — yahyazakaria22 — 2026-11-04
fix: preserve ETA UUID cron backlog progress

- Preserve a remaining-work indicator when an Odoo cron loop starts after its time budget is exhausted.
- Show the unattempted portion of each selected UUID detail window in the batch log.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

f439ab21 — yahyazakaria22 — 2026-11-04
fix: retrieve current-day ETA UUIDs and invoice details

- Retrieve today's invoice and receipt UUID summaries as well as earlier days, then let the detail cron enrich saved UUIDs immediately.
- Limit today's searches to the current time, revisit recent invoice submissions, and complete yesterday's streams after midnight.
- Preserve receipt search checkpoints through the current day, rescan the active hour, and revisit the full day after midnight for late receipts.
- Use the ETA document-details endpoint for invoice enrichment while keeping the working raw endpoint for receipts.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

27c11ebd — yahyazakaria22 — 2026-11-04
fix: pace ETA UUID detail requests by elapsed time

- Pace ETA detail requests by their start times so response latency counts toward the two-per-second limit and the cron uses more of its available time.
- Include elapsed batch time in the UUID detail log to distinguish slow ETA responses from cron scheduling delays.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

6b39c819 — yahyazakaria22 — 2026-11-04
fix: fall back to ETA invoice raw details

- Retry invoice parsing failures using the invoice raw endpoint.

Files changed:

- ab_tax_eta_archive/models/eta_export.py

b63c1c5c — yahyazakaria22 — 2026-11-04
fix: request ETA JSON details and expose fetch diagnostics

- Explicitly request JSON through both ETA detail request format headers.
- Distinguish missing response objects, invalid JSON document text, and missing document fields; retain diagnostics from both invoice endpoints.
- Log successful token acquisition and batch startup without exposing token or document values.
- Load each UUID independently to avoid prefetching a large selected recordset during per-record processing.
- Pace invoice fallback requests as well as primary requests.
- Validation: isolated Python checks passed for four invoice shapes, receipt parsing, invoice tax totals, and rejection of three incomplete response shapes. Live ETA and Odoo database validation still requires server execution.

Files changed:

- ab_tax_eta_archive/models/eta_export.py
- ab_tax_eta_archive/changelog.d

Current changes before commit:

- Retrieve historical receipts through resumable full JSON packages and split oversized intervals.
- Add connection-scoped authenticated callback ping and receipt package notifications.
- Add dashboard document amounts and VAT by currency with detail coverage.
- Maintain Arabic translations for the new configuration and dashboard text.
- Validation: synthetic package, callback authorization, amount, Python/XML syntax and Arabic catalog checks passed. Live Odoo upgrade and ETA calls require server validation; POT export could not run without a configured local database.

Files changed:

- ab_tax_eta_archive/__init__.py
- ab_tax_eta_archive/controllers/__init__.py
- ab_tax_eta_archive/controllers/callback.py
- ab_tax_eta_archive/models/__init__.py
- ab_tax_eta_archive/models/eta_config.py
- ab_tax_eta_archive/models/eta_dashboard.py
- ab_tax_eta_archive/models/eta_document.py
- ab_tax_eta_archive/models/eta_package.py
- ab_tax_eta_archive/models/eta_sync.py
- ab_tax_eta_archive/static/src/js/eta_dashboard.js
- ab_tax_eta_archive/static/src/xml/eta_dashboard.xml
- ab_tax_eta_archive/views/eta_views.xml
- ab_tax_eta_archive/i18n/ar.po
- ab_tax_eta_archive/i18n/ar_001.po
- ab_tax_eta_archive/changelog.d
