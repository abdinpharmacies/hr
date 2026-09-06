Recent relevant commit:

- Commit: `f374b20bd2f922e4babbc3d44e57c011b768cb46`
- Author: Alhassan Hossny
- Date: 2026-09-02
- Original subject: ab_test: add passive sync metadata to test headers
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_test/changelog.d/2026-09-02-ab-test-header-passive-sync.md
  - ab_test/i18n/ar.po
  - ab_test/i18n/ar_001.po
  - ab_test/models/ab_test_models.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_test/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_test/models/ab_test_customer_reference.py
  - ab_test/models/ab_test_models.py
