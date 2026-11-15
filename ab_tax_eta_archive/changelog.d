Current changes before commit:

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
