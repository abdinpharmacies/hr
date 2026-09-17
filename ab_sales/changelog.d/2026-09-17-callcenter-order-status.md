# ab_sales: call-center order status refresh

## Recent commit

Commit: `c945122d71abe2cf365fef90a5ceee5266e2c3c9`

Author: Hossam Elsheikh

Date: 2026-09-16T15:46:17+03:00

Original commit subject: ab_sales: enforce API-only access and display branch bills

- Enforce API-only call-center access and display branch bills.

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

## Current changes before commit:

- Refresh successful unresolved call-center submission logs instead of scanning local sales headers or all branch bills.
- Batch and deduplicate request tokens; validate returned order/invoice identities and stop polling saved orders.
- Preserve previous status on missing responses or branch failure; let healthy branches continue without resubmitting orders.
- Require the provider sale-status capability and document the on-demand Bills page behavior.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-17-callcenter-order-status.md`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/branch_services.py`

Validation: isolated targeted module upgrades; sale ownership and access checks; scoped SQL with a fake connection; client batching, identity validation, outage isolation, rollback, and no-SQL checks; Arabic runtime validation and PO format checks. No production upgrade or external database write. Evidence: `/tmp/ab_api_only_validation/ORDER_STATUS_RESULTS.md`.
