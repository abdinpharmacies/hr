Commit: c6aeeec97a7c7121f8c7507488f3eef06d16f3f8
Author: Hossam Elsheikh
Date: 2026-09-09T12:19:10+03:00
Original commit subject: ab_sales/edit after switching to json-2

User-facing changes:
- Provide sales and callcenter branch integration workflows.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-09-07-branch-api-client.md
- ab_sales/changelog.d/2026-09-09-json2-connections.md
- ab_sales/data/branch_connection_jobs.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/views/ab_sales_branch_rpc_config_views.xml

Current changes before commit:

- Require a positive DB serial on each Branch Connection. Sales and returns use the employee-selected store connection without requiring a matching callcenter replica/default-store mapping; store availability and normal business access restrictions still apply.
- Send DB serial for all eight API methods, including POS sale submission; keep the remote PostgreSQL database name separate.
- Validate stock and return branch identity by DB serial while retaining product, invoice, unit and numeric validation; accept JSON product lists.
- Allow a replacement key owned by a different eligible branch user. Reset verified state and capabilities after credential, connection identity or activation changes.
- Preserve encrypted secret storage and existing uncommitted health-only management changes: no credential rotation/revocation UI or scheduled rotation, with permanent-key metadata supported.
- Simplify Branch Connections: show connection essentials and test results, remove the duplicate name/code, remote record ID and extra timestamp, and place activation, alert owner and timeout under Advanced Settings. Simplify the list columns too.
- Rename Enrollment Required to Verification Required and label the connection status and verified branch clearly, preserving the internal state values.
- Add a manual connection/stock/draft-sale/return testing checklist and maintain the Arabic/English pair using exported Odoo POT references.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-09-13-native-db-serial.md
- ab_sales/data/branch_connection_jobs.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/views/ab_sales_branch_rpc_config_views.xml

Validation from 2026-09-13 (before removing the callcenter replica check):
- Targeted upgrades passed on disposable copies codex_dbserial_branch and codex_dbserial_callcenter using isolated ports and zero cron threads.
- Nine branch check groups and seven callcenter check groups passed, including all eight methods, two native key owners, rejection cases, posting ACLs, return record rules, costs, DB/store identity separation, token ownership, and replay with E-Plus mocked.
- Real JSON-2 HTTP checks passed for two users, product-list responses, missing/invalid credentials across all eight endpoints, wrong DB serials, old-parameter rejection, and RPC denial of decrypt_password without reading real secrets.
- Odoo 19 POT exports completed; both Arabic catalogs passed msgfmt --check-format. Branch Operations and callcenter DB Serial/connection labels differ from English at runtime in ar_001.
- Python/XML parsing and git diff --check passed. Copied branch database retains unrelated missing-model/schema diagnostics; existing callcenter connections lack the new DB serial until configured. Clean installation is the release assumption.
- Actual return-line loading passed with a mocked SQL connection: branch-filtered queries, cost mapping, and creation under the authenticated user.
- Development scripts and detailed results are retained outside addon packages in /tmp/ab_db_serial_validation.

Validation for the 2026-09-14 refinement:
- Targeted ab_sales upgrade passed on isolated codex_selected_branch_callcenter with zero cron threads and alternate ports; no running application database was upgraded.
- Actual POS submission and return preview/posting passed for two employee-selected branch connections with no matching local replica records, with the callcenter default unset and with a different default store.
- Positive serial, returned branch identity, administrator-only testing, required verification, store availability, and existing allowed-store access checks passed. All remote responses were mocked; no E-Plus calls were made.
- Exported the Odoo 19 POT and updated only the existing validation-message references in ar.po and ar_001.po. Both catalogs passed msgfmt --check-format and Arabic action/field labels were verified at runtime.
- Python parsing and working-tree whitespace checks passed. Scripts/results are retained outside the addon in /tmp/ab_selected_branch_validation; disposable database/dump removed after verification.

Validation for the simplified form on 2026-09-14:
- Targeted ab_sales upgrades passed on isolated codex_connection_form_callcenter using alternate ports and zero cron threads. The copy omitted unrelated sales-per-day and stock-cache rows; no source database was changed.
- Native Odoo Form smoke checks passed for creation with automatic name/default administrator/timeout, encrypted key storage, successful Test Connection, visible failure diagnostics, and verification reset after an identity edit. Remote responses were mocked.
- Exported the native POT and appended five new labels to both Arabic catalogs, preserving existing msgids/translations. Both passed msgfmt --check-format; the new status and form section labels differ at runtime in ar_001.
- Python/XML parsing and whitespace checks passed. Evidence is retained outside the addon in /tmp/ab_connection_form_validation. Disposable validation data was removed after the checks.

Scope: source changes only. No deployment, live E-Plus writes, hooks, migrations, or automatic provisioning. Existing unrelated working-tree changes are preserved.
