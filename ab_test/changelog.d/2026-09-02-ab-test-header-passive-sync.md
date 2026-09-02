# AB Test Passive Sync Metadata

## Recent relevant commit

- Commit: `dbde3be9df897d31c37d2256419960b5dd3f4e3a`
- Author: emadco88
- Date: 2026-09-02
- Subject: `ab_test/ UPD`
- Added recent test-model UI and access updates for sync validation.

Files changed:

- `ab_test/models/ab_test_models.py`
- `ab_test/security/ir.model.access.csv`
- `ab_test/views/ab_test_views.xml`

## Current changes before commit

- Add passive sync identity fields `db_serial`, `rec_id`, and `payload_json` to `ab_test_header` and `ab_test_header_relation`.
- Add unique `(db_serial, rec_id)` constraints so same-name passive auto-mapping can validate both target models.
- Relax required header fields so `ab_test_header` can accept partial passive sync records.
- Add Arabic translations for the new field and constraint labels.

Files changed:

- `ab_test/models/ab_test_models.py`
- `ab_test/i18n/ar.po`
- `ab_test/i18n/ar_001.po`
- `ab_test/changelog.d/2026-09-02-ab-test-header-passive-sync.md`
