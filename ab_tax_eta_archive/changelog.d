Current changes before commit:

- Add separate ETA invoice and receipt archives with daily sent and received retrieval streams, UUID deduplication, pagination checks, and visible retry errors.
- Create four downloadable daily Excel files and send files for four days prior to a configured Telegram group after retrieval succeeds, starting from a configurable Telegram date.
- Add ETA connection, POS authentication, and Telegram settings, scheduled jobs, access groups, and Arabic translation catalogs.
- Retrieve older receipts through asynchronous ETA receipt packages, split over-limit windows, and expose package progress on the retrieval screen.
- Use the Telegram Bot API with module-scoped settings until the designated Telegram addon is supplied for integration.
- Group invoice and receipt Excel reports by their Cairo issue date while retaining submission date for ETA retrieval validation.
- Refresh unsent issue-date files when later retrievals add or move documents, and require completed submission streams through yesterday before Telegram delivery.
- Recheck one completed day from the latest 14 submission days per stream on each hourly run to detect late ETA results and status changes.
- Preserve sent Excel files and create numbered correction revisions when report rows change; show the prior revision and label correction messages in Telegram.
- Record the latest completed submission day on delivered files so report readers can see the retrieval coverage date.
- Reject duplicate ETA UUIDs within a retrieval instead of silently collapsing potentially unstable pages or overlapping packages.
- Start new ETA connections from 1 October 2026 by default for submission-day retrieval and issue-date Excel backfill.

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
