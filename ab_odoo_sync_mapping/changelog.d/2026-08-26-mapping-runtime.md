commit: 8c72e6628d71f0e008341fb79385036f19cc62e4
author: emadco88 <emadco88@gmail.com>
date: 2026-08-26 16:07:54 +0300
subject: ab_odoo_sync_mapping/ NEW for reports server

User-facing changes:

- Added a manually installed reporting application for branch registration,
  authenticated upload intake, raw receipt audit records, mapping profiles, and
  branch-aware identities.
- Added OCA `queue_job` apply jobs and a report-side apply feeder cron.
- Exposed only push health/upload routes; pull event and checkpoint routes are
  not part of the reporting runtime.
- Added administrative views and complete Arabic translations for `ar` and
  `ar_001`.

Files changed:

- `ab_odoo_sync_mapping/__init__.py`
- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/controllers/__init__.py`
- `ab_odoo_sync_mapping/controllers/main.py`
- `ab_odoo_sync_mapping/models/__init__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_identity.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/security/ir.model.access.csv`
- `ab_odoo_sync_mapping/data/crons.xml`
- `ab_odoo_sync_mapping/data/queue_jobs.xml`
- `ab_odoo_sync_mapping/views/mapping_views.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/changelog.d/2026-08-26-mapping-runtime.md`

## Current changes before commit:

User-facing changes:

- Changed report mapping from synchronous manual apply and minute-based recovery
  to event-driven queue jobs with a two-hour recovery cron.
- Added profile-specific automatic and manual feeder jobs for profile changes,
  mapping changes, manual queueing, backlog continuation, and cron recovery.
- Kept immediate per-record apply job creation for active auto-apply uploads and
  hardened duplicate prevention for already queued records and mirror targets.
- Renamed the profile action to `Queue Pending Uploads` and updated Arabic
  translations for both `ar` and `ar_001`.
- Added a bounded `19.0.1.2.0` migration that updates the deployed recovery cron
  interval without replacing cron, uploads, queue jobs, profiles, or mappings.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/data/crons.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/migrations/19.0.1.2.0/post-migration.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/views/mapping_views.xml`
- `ab_odoo_sync_mapping/changelog.d/2026-08-26-mapping-runtime.md`
