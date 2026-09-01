commit: ccf3ea2877884b78e39ed13ed9d12bd1a0712a44
author: Alhassan Hossny <alhassan.hossny@gmail.com>
date: 2026-09-01 12:54:40 +0300
subject: ab_odoo_sync/ add sync setup script and documentation

User-facing changes:

- Added an Odoo shell setup script for branch and report sync configuration.
- Documented required modules, config keys, selected model data, relation mapping
  rules, and verification steps for the sync process.

Files changed:

- ab_odoo_sync/scripts/configure_sync.py
- ab_odoo_sync/readme.md
- ab_odoo_sync/changelog.d/2026-09-01-sync-setup-script.md

## Current changes before commit:

User-facing changes:

- Documented report-side mapping as event-driven, with the cron retained as a
  two-hour recovery mechanism.
- Added production update notes for the `ab_odoo_sync_mapping` 19.0.1.2.0
  targeted upgrade, cron preservation, queue workers, and mirror uniqueness.
- Updated the test guide to use `Queue Pending Uploads` and explain that raw-only
  handling occurs after the queued feeder runs.

Files changed:

- ab_odoo_sync/readme.md
- ab_odoo_sync/test-guide.md
- ab_odoo_sync/changelog.d/2026-09-01-sync-setup-script.md
