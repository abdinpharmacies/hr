# ab_sales: API-only call-center and branch bills

## Recent commit

Commit: `17a116c8f756286a27198bf1ec2c76001c986ed8`

Author: Hossam Elsheikh

Date: 2026-09-16T10:57:48+03:00

Original commit subject: ab_sales: send and validate store identity in Branch API requests

- Send and validate database/store identities for branch requests and responses.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-15-shared-sales-api.md`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`

## Current changes before commit:

- Enforce API-only transport for all call-center users and jobs through inherited connector guards and process-level role selection.
- Route customer operations, all-store balance dialogs, and existing inventory/history/status refreshes through branch endpoints; preserve caches on failure.
- Show branch bills through the Bills menu and POS search, with branch/type/status filters, stable pagination, notes, printing, and remote return opening.
- Mark stale balances, retain request tokens after uncertain writes, validate provider capabilities, and maintain both Arabic translations.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-16-api-only-callcenter.md`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/access_policy.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_only_connector.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/security/ir.model.access.csv`
- `ab_sales/static/src/add_products/add_products_action.js`
- `ab_sales/static/src/add_products/product_card.xml`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.xml`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action_sales_line_balance.xml`
- `ab_sales/views/bill_wizard_action.xml`
- `ab_sales/views/product_store_balance_qweb.xml`
- `ab_sales/views/sales_header.xml`

Validation: isolated targeted upgrades, mocked SQL/HTTP boundary and cache tests, real native-bearer JSON-2 bill requests, rendered OWL Bills-page checks, and Arabic catalog/runtime checks. No production SQL writes or deployment. Detailed evidence: `/tmp/ab_api_only_validation/RESULTS.md`.
