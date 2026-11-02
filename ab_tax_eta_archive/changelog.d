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

Current changes before commit:

- Retrieve historical sent and received receipts through ETA receipt packages instead of the recent-only search API.
- Resume package requests, split oversized windows, and download completed JSON packages on Retry or cron.
- Preserve recent issued-time searches and count historical package results by received time.

Files changed:

- ab_tax_eta_archive/models/eta_sync.py
