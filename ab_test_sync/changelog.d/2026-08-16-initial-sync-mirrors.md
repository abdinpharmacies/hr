## Commit c9d780d

Author: Alhassan Hossny
Date: 2026-08-16
Subject: ab_test_sync/mediator module for ab_test, sync testing

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

## Current changes before commit

User-facing changes:

- Added typed MAIN mirror models for cascade, set-null, and restrict delete policy tests.
- Registered all six new test source models for branch upload capture.
- Added apply profiles and active field mappings for parent/child delete-policy payloads.
- Mapped child `parent_id` through source-ID relation resolution, with optional relation handling for the set-null case.
- Added read-only mirror views and menus that keep inactive archived records visible.
- Added Arabic translations for the new synced delete-policy screens and model labels.

Files changed:

- `ab_test_sync/changelog.d/2026-08-16-initial-sync-mirrors.md`
- `ab_test_sync/data/sync_profiles.xml`
- `ab_test_sync/i18n/ar.po`
- `ab_test_sync/i18n/ar_001.po`
- `ab_test_sync/models/ab_test_sync_models.py`
- `ab_test_sync/security/ir.model.access.csv`
- `ab_test_sync/security/record_rules.xml`
- `ab_test_sync/views/ab_test_sync_views.xml`
