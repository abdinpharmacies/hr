## c28870f9ed15e97d73c14387f65b0b47821fd7ac

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Sun Aug 23 17:01:20 2026 +0300
- Subject: ab_odoo_sync/Tracked branch record changes create Upload Outbox events, each event ensures a queue_job sender is queued, and the queue runner asynchronously sends pending outbox batches to MAIN

User-facing changes:

- Added queued branch upload sending and queue job registration for upload apply work.

Files changed:

- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/sync-rules.md`

## Current changes before commit:

User-facing changes:

- Documented Rule 3: `__sync` mirror models must not define required fields.
- Added apply-profile validation that rejects mirror target models with required fields, so strictness is controlled by field mapping `required` flags instead of table schema.

Files changed:

- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/sync-rules.md`
