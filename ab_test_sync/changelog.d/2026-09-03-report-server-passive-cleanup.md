Recent relevant commit:

- Commit: `42cef3cf5bae75651ee80c74e209a4a9cfd72e8b`
- Author: emadco88
- Date: 2026-08-26
- Original subject: ab_test_sync/ UPD
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_test_sync/__manifest__.py
  - ab_test_sync/changelog.d/2026-08-25-sync-model-required-fields.md
  - ab_test_sync/data/customer_reference_sync_profiles.xml
  - ab_test_sync/data/sync_profiles.xml

Current changes before commit:

- User-facing changes:
  - Added passive sync metadata inheritance for classified high-value report facts where applicable.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_test_sync/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_test_sync/__manifest__.py
  - ab_test_sync/models/ab_test_customer_reference_sync.py
  - ab_test_sync/models/ab_test_sync_models.py
