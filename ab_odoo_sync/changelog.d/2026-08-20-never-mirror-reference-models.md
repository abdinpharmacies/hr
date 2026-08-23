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

- Rename `never-mirror.md` to `sync-rules.md` and document the branch upload boundary as enforceable sync rules.
- Add Rule 2 for `res.users` dependent mirrored models, requiring corresponding `__sync` relations to target `ab_users`.
- Add central Odoo Sync rule checks so protected master models and `res.users` cannot be branch upload sources or branch mirrored source models.
- Restrict branch snapshots to enabled apply-profile fields and serialize protected master/user relations as source IDs only.
- Ignore protected relation details during MAIN placeholder creation, even if an older queued payload still contains display names or stable-key values.
- Resolve user force-ID references through the standalone MAIN-side `ab_users` module instead of defining user placeholders inside `ab_odoo_sync`.
- Preserve upload source write dates from the source record metadata instead of relying on payload fields.
- Add Arabic translations for the new validation messages.

Files changed:

- `ab_odoo_sync/sync-rules.md`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync/models/ab_odoo_sync_rules.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/models/ab_odoo_sync_identity.py`
- `ab_odoo_sync/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync/models/ab_odoo_sync_upload_source.py`
