Commit: c6aeeec97a7c7121f8c7507488f3eef06d16f3f8
Author: Hossam Elsheikh
Date: 2026-09-09T12:19:10+03:00
Original commit subject: ab_sales/edit after switching to json-2

User-facing changes in the referenced commit:
- Update branch connections for the JSON-2 transport.

Current changes before commit:

- Move the configured-IP routing overrides into the new ab_sales_routing bridge; restore the original connection helpers in ab_sales. The bridge also covers cashier routing.
- Keep routing validation and safe sale/return connection diagnostics in ab_sales_routing; retain callcenter API status and frontend error-display changes here.
- Show business RPC details throughout POS notifications and use translated fallback messages for technical exceptions.
- Check the employee-selected branch through the existing authenticated status API, preserving DB serial, verification and store-access checks. Keep the status endpoint Boolean and make no direct SQL probe or persistent health update.
- Label the status as Branch API connected/unavailable; show failure details and discard stale responses after branch changes. Local branch POS retains its SQL status check.
- Document the API/E-Plus distinction and safe diagnostic checks; maintain both Arabic catalogs using native Odoo POT references.
- Preserve earlier uncommitted DB serial, native credential and connection-form work; its details are recorded in the 2026-09-13 changelog entry.

Files changed (current module working tree):
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-09-13-native-db-serial.md
- ab_sales/changelog.d/2026-09-14-pos-connectivity.md
- ab_sales/data/branch_connection_jobs.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/views/ab_sales_branch_rpc_config_views.xml

Validation:
- Targeted upgrades completed on isolated codex_pos_connectivity_branch and codex_pos_connectivity_callcenter; no application database was upgraded. Copies omitted large unrelated sales-day/inventory cache rows and did not include filestores.
- Routing and connector tests passed in both registries for default/non-default stores, blank addresses, branch-scoped endpoints, preserved business/access errors and sanitized driver errors.
- Branch regression checks passed for all eight API methods, two native-key owners, invalid/expired/revoked/inactive/admin/session-only rejection, business ACLs, costs, differing DB/store identifiers, record rules and operation-token isolation. E-Plus was mocked.
- Callcenter regression checks passed for independently selected sale/return connections without local default-store mapping. API status passed with SQL probes blocked, plus wrong identity, invalid credential, network/server error, unverified/inactive connection and unauthorized-store rejection.
- JavaScript checks passed for error extraction, safe technical-error fallback, status failures and stale-response handling. Python/XML parsing and JavaScript syntax checks passed.
- Native POT exports and all four Arabic msgfmt --check-format checks passed. Runtime translation results are retained with the validation evidence.
- The branch copy retains pre-existing missing-module/table diagnostics; copies also lack attachment files. These did not prevent the targeted upgrades or assertions.
- Scripts, POTs and results are retained outside addon packages in /tmp/ab_pos_connectivity_validation.

Scope: no deployment, server restart, real E-Plus connection or business write, store-IP change, API version change, new connection field, hook or migration. Existing unrelated working-tree changes remain intact.

Bridge refinement: ab_sales_routing installs and passes routing/cashier/API tests
against isolated branch and callcenter registries. The callcenter test uses an
isolated addons-path overlay because its workspace root is not writable. No
running database or server configuration was changed.
