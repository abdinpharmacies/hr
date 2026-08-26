## ea0b8e93ae2ce06bd8641e6049166fee4d2ace78

- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: Thu Aug 20 11:20:57 2026 +0300
- Subject: ab_test_sync/adding some relations to test force id

User-facing changes:

- Added test sync relations for validating force-ID reference handling.

Files changed:

- `ab_test_sync/models/ab_test_sync_models.py`

## Current changes before commit:

User-facing changes:

- Connected report-side test mirrors to `ab_odoo_sync_mapping` without depending
  on operational source models or the upload capture runtime.
- Removed upload-source declarations from report mapping data.

Files changed:

- `ab_test_sync/__manifest__.py`
- `ab_test_sync/data/customer_reference_sync_profiles.xml`
- `ab_test_sync/data/sync_profiles.xml`
- `ab_test_sync/changelog.d/2026-08-25-sync-model-required-fields.md`
