# ab_branch_api: call-center order status refresh

## Recent commit

Commit: `d5b2c66d3d8d07b1b9a3aa470a6fe79b20e070fe`

Author: Hossam Elsheikh

Date: 2026-09-16T15:31:42+03:00

Original commit subject: ab_branch_api: add services for API-only call-center workflows

- Add API-only call-center services and branch bill access.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-16-api-only-callcenter.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/models/summary.md`
- `ab_branch_api/security/ir.model.access.csv`

## Current changes before commit:

- Add token-scoped status reads for sales owned by the authenticated integration user and selected store.
- Read E-Plus status only for the requested owned pending sales; omit missing or inaccessible orders without replaying operations.
- Advertise the new capability and document targeted refresh with both Arabic translations.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-callcenter-order-status.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/callcenter_services.py`

Validation: isolated targeted module upgrades; sale ownership and access checks; scoped SQL with a fake connection; client batching, identity validation, outage isolation, rollback, and no-SQL checks; Arabic runtime validation and PO format checks. No production upgrade or external database write. Evidence: `/tmp/ab_api_only_validation/ORDER_STATUS_RESULTS.md`.
