# ab_branch_api: API-only call-center and branch bills

## Recent commit

Commit: `8b860aca46599c055fb9c5823f9be075760bae40`

Author: Hossam Elsheikh

Date: 2026-09-16T09:57:38+03:00

Original commit subject: ab_branch_api/consolidate store-scoped workflows and return employee validation

- Consolidate store-scoped branch workflows and return employee validation without changing ordinary branch sales.

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

## Current changes before commit:

- Add authenticated customer, product balance, inventory/history snapshot, and invoice-status services for API-only call-center operation.
- Expose branch Odoo bill search, details, authorized notes updates, and print rendering with database/store-qualified references.
- Keep snapshot pages fixed and user/store scoped; preserve customer operation tokens and uncertain outcomes.
- Advertise new capabilities and document rollout with no changes to other branch addons.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-16-api-only-callcenter.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/security/ir.model.access.csv`

Validation: isolated targeted upgrades, mocked SQL/HTTP boundary and cache tests, real native-bearer JSON-2 bill requests, rendered OWL Bills-page checks, and Arabic catalog/runtime checks. No production SQL writes or deployment. Detailed evidence: `/tmp/ab_api_only_validation/RESULTS.md`.
