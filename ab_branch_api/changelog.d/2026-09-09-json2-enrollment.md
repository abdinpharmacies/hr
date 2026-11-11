Commit: b962b4291a29342d95eb1017a33094bd1281c13d
Author: Hossam Elsheikh
Date: 2026-09-08 14:12:22 +0300
Subject: ab_branch_api/feat: add reusable branch API for callcenter integration

User-facing changes:
- Provide branch-scoped product/stock, sales, returns, and operation-status methods backed by branch business logic.

Files changed:
- ab_branch_api/__init__.py
- ab_branch_api/__manifest__.py
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/security/ir.model.access.csv
- ab_branch_api/security/security_groups.xml
- ab_branch_api/views/api_views.xml
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/changelog.d/2026-09-07-branch-api.md

Current changes before commit:

Author: Hossam Elsheikh
Date: 2026-09-09

- Declare native JSON-2 support through Odoo's rpc dependency; release version 19.0.2.0.0.
- Add administrator enrollment with an existing non-administrator service user, explicit store permissions, 90-day native API keys, and acknowledgment of database-wide programmatic key management.
- Display enrollment secrets once without storing plaintext on the branch.
- Expose authenticated credential metadata and user/store-scoped, retry-safe key retirement using native Odoo key controls.
- Add English/Arabic enrollment UI for ar and ar_001.

Validation:
- Targeted ab_branch_api upgrade completed on abdin_pos. Existing unrelated missing-model/table warnings remain in that database.
- Real JSON-2 HTTP tests passed for native bearer authentication, missing/invalid keys, scoped metadata, and cross-store denial. Temporary test key revoked afterward.
- Native enrollment/generation/revocation and idempotent retirement passed with transaction rollback; no E-Plus calls or business writes.
- Exported Odoo POT; both PO files passed msgfmt format validation. The enrollment action differs between en_US and ar_001 at runtime.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/models/__init__.py
- ab_branch_api/models/credentials.py
- ab_branch_api/security/ir.model.access.csv
- ab_branch_api/security/security_groups.xml
- ab_branch_api/views/enrollment_views.xml
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/changelog.d/2026-09-07-branch-api.md
- ab_branch_api/changelog.d/2026-09-09-json2-enrollment.md
