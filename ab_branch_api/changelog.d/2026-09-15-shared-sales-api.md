# ab_branch_api: branch API workflows

## Recent commit

Commit: `055c5860396c7e3823696e0ce645f1d4c0c00b4f`

Author: Hossam Elsheikh

Date: 2026-09-14T15:19:56+03:00

Original commit subject: ab_branch_api/use native API keys and DB serial identity

- Authenticate branch calls with native API keys and configured DB serial identity.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-13-native-db-serial.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/credentials.py`
- `ab_branch_api/security/ir.model.access.csv`
- `ab_branch_api/security/security_groups.xml`
- `ab_branch_api/views/api_views.xml`
- `ab_branch_api/views/enrollment_views.xml`

## Current changes before commit:

- Resolve optional explicit/default stores separately from native bearer and DB identity validation; allow metadata checks without a store.
- Own the stock reader and API-scoped inventory/return overrides in Branch API; leave branch ab_sales source and ordinary workflows unchanged.
- Reuse existing posting and conversion methods; filter legacy return header reads through an API-only adapter without copying external writes.
- Pin the existing sales endpoint per request, isolate SQL connections, and prevent automatic reconnect/replay after processing starts.
- Validate return employees in the provider before external processing or reservation; preserve replay and reconciliation.
- Document coordinated rollout, manual routing-addon removal, and employee-extension retirement; maintain both Arabic catalogs.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-15-shared-sales-api.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/credentials.py`
- `ab_branch_api/models/routing.py`
- `ab_branch_api/models/sales_workflow.py`
