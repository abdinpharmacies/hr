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
