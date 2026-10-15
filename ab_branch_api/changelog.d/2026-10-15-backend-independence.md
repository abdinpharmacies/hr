## 3033a2a164214a4f04c1e46585f453c0fd0cacc8 — Alhassan Hossny — 2026-10-13

Original commit subject: ab_branch_api: fix live stock validation and callcenter customer registration

User-facing changes:
- Validate live branch stock and import verified callcenter customers.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-12-callcenter-validation.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/callcenter_services.py
- ab_branch_api/models/customer_sync.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/models/sale_validation.py
- ab_branch_api/security/ir.model.access.csv

## Current changes before commit:

- Delegate backend-dependent endpoints to ab_sales while retaining authentication, validation, pagination and operation journaling.
- Remove API-owned external SQL, connectors, routing pools and backend transaction/recovery wrappers.
- Keep all 20 endpoint signatures and existing token/revision/replay behavior; use committed stock validation.
- Document backend ownership, rollout order and validation results.

Files changed:
- ab_branch_api/BRANCH_API_BACKEND_INDEPENDENCE_PLAN.md
- ab_branch_api/README.md
- ab_branch_api/changelog.d/2026-10-15-backend-independence.md
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/callcenter_services.py
- ab_branch_api/models/customer_sync.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/models/reconciliation.py
- ab_branch_api/models/routing.py
- ab_branch_api/models/sale_validation.py
- ab_branch_api/models/sales_workflow.py

Validation:
- 27 mocked backend/transport checks passed outside production addon packages.
- Development database `abdin_old_pos19`: targeted sales upgrade followed by Branch API upgrade passed.
- Python registry loading, Arabic runtime menu rendering and translation format checks passed.
- External posting was mocked; live end-to-end posting remains deployment acceptance work.
