## 009977908d7046630ecdb3313b94a52a52ca53d0

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Tue Aug 25 10:56:32 2026 +0300
- Subject: ab_odoo_sync: enforce report sync schema rules

User-facing changes:

- Enforced permissive mirror schemas and moved required-value checks into apply-profile mappings.
- Switched Odoo Sync jobs to the Integration Queue Job provider used by the reporting environment at that time.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`
- `ab_odoo_sync/changelog.d/2026-08-25-sync-model-required-fields.md`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/sync-rules.md`

## Current changes before commit:

User-facing changes:

- Use the available OCA `queue_job` addon for all Odoo Sync background work.
- Register upload apply, MAIN apply feeder, and branch sender jobs on `queue_job.channel_root`.
- Remove the runtime dependency on the deleted `integration_queue_job` wrapper.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`
- `ab_odoo_sync/changelog.d/2026-08-25-sync-model-required-fields.md`
