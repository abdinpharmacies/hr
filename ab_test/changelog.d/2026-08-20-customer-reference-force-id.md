## Current changes before commit:

User-facing changes:

- Added a customer-reference source model for testing force-ID behavior against MAIN-owned `ab_customer` records.
- Added security and menu access for creating customer-reference test rows from the AB Sync Test menu.
- Added `ab_customer` as an explicit module dependency for the customer relation.

Files changed:

- `ab_test/__manifest__.py`
- `ab_test/models/__init__.py`
- `ab_test/models/ab_test_customer_reference.py`
- `ab_test/i18n_extra/ar.po`
- `ab_test/i18n_extra/ar_001.po`
- `ab_test/security/customer_reference_access.xml`
- `ab_test/security/customer_reference_rules.xml`
- `ab_test/views/ab_test_customer_reference_views.xml`
- `ab_test/changelog.d/2026-08-20-customer-reference-force-id.md`
