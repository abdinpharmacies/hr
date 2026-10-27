# Immediate manual mapping reapplication

Recent relevant commit: `1a0282cbc17619acc773e996288d9e96bc0a5d53`
Author: emadco88-report-server
Date: 2026-10-07
Original subject: ab_odoo_sync_mapping/ FIX it should not refuse to receive any authnicated payload

Current changes before commit:

- Run Reapply Mapping synchronously without creating receipt, feeder, or apply jobs, including when Automatically Queue Apply is disabled.
- Check upload write access before privileged application; require the current active apply-capable source profile without generating profiles.
- Reuse current mappings, per-upload overrides, existing branch identity, target validation, and application tracking.
- Keep successful records when another application fails; report applied, partial, failed, and busy/skipped totals.
- Use normal savepoints to roll back failed target changes and clear ORM caches before continuing.
- Lock each upload and advance its application generation so older queued jobs cannot overwrite the manual result.
- Document synchronous execution and request timeout behavior; add English button help and Arabic translations.
- Bump the module version to 19.0.1.6.2.

Validation and deployment:

- 40 manual reapply checks passed on sync_receipts_test_20261006, including actual partner updates, override handling, mixed results, rollback after target writes, obsolete queued-job execution, busy records, and unauthorized callers.
- All 34 automatic-queue regression checks passed. Test fixtures were rolled back; scripts remain under /opt/odoo19/validation/sync_manual_reapply and /opt/odoo19/validation/sync_auto_queue.
- Isolated targeted module upgrade passed; XML and both Arabic catalogs passed parsing and message checks.
- Saved production schema, relevant module metadata, addon candidate, and profile configuration under /opt/odoo19/resource-tuning-backups/20261026-manual-reapply. This is a bounded deployment backup, not a full business-data dump.
- Upgraded only ab_odoo_sync_mapping on report19 to installed version 19.0.1.6.2 and restarted odoo19.service. Both updated button views are present.
- Queue runner remains inactive. Before/after profile snapshots match exactly. No production upload was manually applied or backlog replayed during verification.

Files changed:

- `__manifest__.py`
- `README.md`
- `models/ab_odoo_sync_upload_record.py`
- `views/mapping_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-26-immediate-reapply.md`
