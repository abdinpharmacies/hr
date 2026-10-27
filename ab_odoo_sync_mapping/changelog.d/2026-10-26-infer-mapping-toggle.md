# Infer mapping type when enabling sync

Recent relevant commit: `1a0282cbc17619acc773e996288d9e96bc0a5d53`
Author: emadco88-report-server
Date: 2026-10-07
Original subject: ab_odoo_sync_mapping/ FIX it should not refuse to receive any authnicated payload

Current changes before commit:

- Share toggle normalization between profile mappings and per-upload overrides through an abstract mixin.
- Disabled mappings select Ignore, clear Required, and count as intentionally handled for ordinary and archive application.
- Re-enabling infers the current compatible scalar or relation type, without storing a previous mapping type. Enabled creation without an explicit type also infers it; explicit enabled types remain validated normally.
- Select permitted stable-key mappings when both keys are configured, preserving source-ID-only relation and user-placeholder restrictions.
- Fall back to installed source metadata for overrides whose snapshots omit field types. Unsupported, missing, protected, and one-to-many mappings remain Ignore for manual configuration.
- Preserve targets and relation settings while disabled. Apply identical behavior to editor onchange, ORM creation, imports, and bulk writes.
- Make Mapping Type readonly while disabled, add English and Arabic toggle help, and document current inference behavior.
- Add bounded end-stage normalization of existing disabled rows, suppressing feeder creation. Bump the module to 19.0.1.7.2.

Validation and production deployment:

- 31 inference checks passed on actual business/reporting models, covering scalar, many-to-one, many-to-many, stable keys, relation restrictions, source audit fields, overrides, archive handling, bulk writes, editor changes, and migration repeatability.
- All 29 audit/ignore, 53 direct-upload, and 40 immediate-reapply regression checks passed (153 checks total).
- Isolated targeted upgrade, Python/XML parsing, both Arabic catalogs, and git diff --check passed.
- Backed up module configuration to /opt/odoo19/resource-tuning-backups/20261026-sync-infer/configuration.dump and upgraded only ab_odoo_sync_mapping on report19 to installed version 19.0.1.7.2.
- Verified all 27 existing disabled profile mappings are Ignore with Required false; there are no previous_mapping_type fields on either mapping model.
- Before/after snapshots of enabled mappings/overrides, full profile settings, queue count, and upload 729384 match exactly. No reapplication or backlog replay was run.
- Restarted Odoo and the already-running queue runner, preserving their running states. Login endpoint returns HTTP 200.
- Test scripts/logs remain outside the production addon under /opt/odoo19/validation/sync_infer, /opt/odoo19/validation/sync_toggle, and /tmp/sync-infer-*.log.

Files changed:

- `__manifest__.py`
- `README.md`
- `models/__init__.py`
- `models/ab_odoo_sync_mapping_toggle_mixin.py`
- `models/ab_odoo_sync_apply_profile.py`
- `models/ab_odoo_sync_upload_override.py`
- `models/ab_odoo_sync_upload_record.py`
- `views/mapping_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `migrations/19.0.1.7.2/end-migration.py`
- `changelog.d/2026-10-26-infer-mapping-toggle.md`
