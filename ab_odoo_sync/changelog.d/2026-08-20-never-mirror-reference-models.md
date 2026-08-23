## fe1ea3b35c5d842755626afc909265f1516df6ea

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Thu Aug 20 11:21:33 2026 +0300
- Subject: ab_odoo_sync/added never-mirror.md list and update the changelog

User-facing changes:

- Documented the first master/reference model boundary for branch-to-MAIN uploads.
- Listed product, UoM, doctor, customer, store, supplier, contract, cost center, and employee reference models as never-mirror models.
- Clarified that missing referenced master records should be force-ID placeholders, then later resolved by MAIN/master-data updates.

Files changed:

- `ab_odoo_sync/never-mirror.md`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`

## Current changes before commit:

User-facing changes:

- Use the already installed OCA `queue_job` provider for Odoo Sync background jobs.
- Stop forcing installation of `integration_queue_job`, which collides with `queue_job` on the unique root queue channel.
- Queue branch Upload Outbox sending through `queue_job` from both the Send Now action and the Branch Upload cron.
- Automatically enqueue the branch upload sender when a new upload outbox event is captured.
- Keep the existing branch-to-MAIN HTTP batch sender as the queued worker body so failed outbox rows still record their error details.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/models/ab_odoo_sync_upload_record.py`
