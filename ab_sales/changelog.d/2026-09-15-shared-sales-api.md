# ab_sales: branch API workflows

## Recent commit

Commit: `ff76031588e8409380420d708539a9e63efeadbd`

Author: Hossam Elsheikh

Date: 2026-09-14T15:12:16+03:00

Original commit subject: ab_sales/Added branch API requests using native API keys and DB serial. Updated branch connection settings, connection testing, and status handling. Routed stock, sales, and returns through the selected branch. Added request tokens, response identity checks, and operation logging. Added return employee selection and session validation. Updated documentation and both Arabic translation catalogs.

- Add native-key branch connections, JSON-2 business requests, response identity checks and return employee selection/session validation.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-13-native-db-serial.md`
- `ab_sales/changelog.d/2026-09-14-pos-connectivity.md`
- `ab_sales/changelog.d/2026-09-14-return-employee.md`
- `ab_sales/data/branch_connection_jobs.xml`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`
- `ab_sales/views/ab_sales_branch_rpc_config_views.xml`
- `ab_sales/views/ab_sales_return.xml`

## Current changes before commit:

- Send the existing connection store E-Plus serial alongside DB serial through the native JSON-2 adapter.
- Validate DB/store identity for connection tests, stock envelopes, sale/return results and nested operation status, including empty responses.
- Reject mismatched stock-row stores and return-line invoice/store identity.
- Update the contract version metadata and workflow guide for API-owned stock/return adaptations and coordinated rollout without a branch ab_sales upgrade; verify existing Arabic message pairs.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-15-shared-sales-api.md`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
