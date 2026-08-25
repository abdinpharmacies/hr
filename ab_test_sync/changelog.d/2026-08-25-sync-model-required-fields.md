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

- Made Test Sync mirror identity fields optional so test `__sync` models follow the same schema-permissive rule as production mirrors.

Files changed:

- `ab_test_sync/models/ab_test_sync_models.py`
