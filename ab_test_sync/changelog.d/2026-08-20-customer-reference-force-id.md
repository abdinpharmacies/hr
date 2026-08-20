## Current changes before commit:

User-facing changes:

- Added a typed customer-reference mirror model for testing force-ID behavior against MAIN-owned `ab_customer` records.
- Added upload-source and auto-apply profile data with `customer_id` mapped as `sync_many2one`.
- Added read-only mirror security and menu access for inspecting customer-reference sync rows.

Files changed:

- `ab_test_sync/__manifest__.py`
- `ab_test_sync/models/__init__.py`
- `ab_test_sync/models/ab_test_customer_reference_sync.py`
- `ab_test_sync/i18n_extra/ar.po`
- `ab_test_sync/i18n_extra/ar_001.po`
- `ab_test_sync/security/customer_reference_access.xml`
- `ab_test_sync/security/customer_reference_rules.xml`
- `ab_test_sync/data/customer_reference_sync_profiles.xml`
- `ab_test_sync/views/ab_test_customer_reference_sync_views.xml`
- `ab_test_sync/changelog.d/2026-08-20-customer-reference-force-id.md`
