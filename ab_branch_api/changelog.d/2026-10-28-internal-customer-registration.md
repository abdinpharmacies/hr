## 23d38d94a - Hossam Elsheikh - 2026-09-16

Original commit subject: ab_branch_api: add services for API-only call-center workflows

User-facing changes:
- Added authenticated branch customer registration with a separate Odoo customer-create permission check.

Files changed:
- ab_branch_api/models/callcenter_services.py
- ab_branch_api/security/ir.model.access.csv

## 12f3c4f02 - Alhassan Hossny - 2026-10-13

Original commit subject: ab_branch_api: fix live stock validation and callcenter customer registration

User-facing changes:
- Serialized branch customer registration to prevent concurrent spare-record claims.

Files changed:
- ab_branch_api/models/callcenter_services.py

## Current changes before commit:

- Let authenticated internal branch API users with sale-posting access register customers without Odoo customer-create permission.
- Keep the existing store scope, registration lock, request token, and spare-record workflow.

Files changed:
- ab_branch_api/models/callcenter_services.py
- ab_branch_api/changelog.d/2026-10-28-internal-customer-registration.md
