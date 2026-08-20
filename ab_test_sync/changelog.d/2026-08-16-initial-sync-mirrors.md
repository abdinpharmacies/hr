## Current changes before commit

User-facing changes:

- Added four typed MAIN mirror models with the `__sync` suffix for test categories, tags, headers, and lines.
- Preserved complete raw source payloads alongside selected typed fields and synchronization metadata.
- Added branch/source identity constraints and relational links between mirror records.
- Registered all four test source models for full-payload branch capture.
- Added inactive-by-default field mapping profiles so MAIN controls which payload fields populate typed mirrors.
- Added read-only mirror menus and administration views.
- Added complete Arabic translations for both supported Arabic locales.

Files changed:

- `ab_test_sync/__init__.py`
- `ab_test_sync/__manifest__.py`
- `ab_test_sync/changelog.d/2026-08-16-initial-sync-mirrors.md`
- `ab_test_sync/data/sync_profiles.xml`
- `ab_test_sync/i18n/ar.po`
- `ab_test_sync/i18n/ar_001.po`
- `ab_test_sync/models/__init__.py`
- `ab_test_sync/models/ab_test_sync_models.py`
- `ab_test_sync/security/ir.model.access.csv`
- `ab_test_sync/security/record_rules.xml`
- `ab_test_sync/security/security_groups.xml`
- `ab_test_sync/views/ab_test_sync_views.xml`
