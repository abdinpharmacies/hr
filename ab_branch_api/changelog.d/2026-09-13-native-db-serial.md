Commit: 34781a7e41d14d361d38364d48465fbd80817633
Author: Hossam Elsheikh
Date: 2026-09-09T12:15:01+03:00
Original commit subject: ab_branch_api/switching to json-2

User-facing changes:
- Introduce the branch JSON-2 API and credential metadata.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-09-07-branch-api.md
- ab_branch_api/changelog.d/2026-09-09-json2-enrollment.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/credentials.py
- ab_branch_api/security/ir.model.access.csv
- ab_branch_api/security/security_groups.xml
- ab_branch_api/views/enrollment_views.xml

Current changes before commit:

- Require native Odoo bearer verification and executing-user ownership on every version 1 method; reject inactive, external and administrator users and session-only requests.
- Replace store_serial with a positive configured DB serial and resolve the active replica default sales store, checking store availability, allowed stores and record access.
- Remove preparation, generated credentials, dedicated API roles, manual bindings, and API-specific posting/cost flags. Retain administrator operation diagnostics.
- Enforce sales/return business ACLs and existing-record access before business workflows; report posting capability from ACLs and include costs for eligible callers.
- Return DB serial in capabilities, status, stock rows and return snapshots; enforce token ownership across users and stores.
- Mark the inherited password helper private to RPC while preserving internal delegation; return only metadata for natively authenticated unexpired credentials.
- Document external provisioning and the shared DB serial contract; preserve existing Arabic entries and append new messages to both catalogs.

Files changed:
- ab_branch_api/README.md
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-09-13-native-db-serial.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/credentials.py
- ab_branch_api/security/ir.model.access.csv
- ab_branch_api/security/security_groups.xml
- ab_branch_api/views/api_views.xml
- ab_branch_api/views/enrollment_views.xml

Validation:
- Targeted upgrades passed on disposable copies codex_dbserial_branch and codex_dbserial_callcenter using isolated ports and zero cron threads.
- Nine branch check groups and seven callcenter check groups passed, including all eight methods, two native key owners, rejection cases, posting ACLs, return record rules, costs, DB/store identity separation, token ownership, and replay with E-Plus mocked.
- Real JSON-2 HTTP checks passed for two users, product-list responses, missing/invalid credentials across all eight endpoints, wrong DB serials, old-parameter rejection, and RPC denial of decrypt_password without reading real secrets.
- Odoo 19 POT exports completed; both Arabic catalogs passed msgfmt --check-format. Branch Operations and callcenter DB Serial/connection labels differ from English at runtime in ar_001.
- Python/XML parsing and git diff --check passed. Copied branch database retains unrelated missing-model/schema diagnostics; existing callcenter connections lack the new DB serial until configured. Clean installation is the release assumption.
- Actual return-line loading passed with a mocked SQL connection: branch-filtered queries, cost mapping, and creation under the authenticated user.
- Development scripts and detailed results are retained outside addon packages in /tmp/ab_db_serial_validation.

Scope: source changes only. No deployment, live E-Plus writes, hooks, migrations, or automatic provisioning. Existing unrelated working-tree changes are preserved.
