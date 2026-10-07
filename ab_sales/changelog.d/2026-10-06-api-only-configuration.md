# ab_sales: API-only callcenter configuration

## Recent commit

Commit: `42b13eaf32fa5dafbe2e16bb9e0e266e5ba570a0`

Author: Hossam Elsheikh

Date: 2026-09-17T16:33:15+03:00

Original commit subject: ab_sales: persist callcenter bills locally and improve branch submission recovery

- Preserved local bills, offline printing, and recovery using original submission tokens.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-17-local-callcenter-bills.md`
- `ab_sales/data/ir_cron.xml`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/models/local_bills.py`
- `ab_sales/security/ir.model.access.csv`
- `ab_sales/security/local_bill_rules.xml`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.xml`
- `ab_sales/static/src/bill_wizard/local_bill_list.js`
- `ab_sales/views/ab_sales_return.xml`
- `ab_sales/views/local_bill_views.xml`
- `ab_sales/views/sales_header.xml`

## Current changes before commit:

- Store administrator-only API keys as masked plaintext; block exports and invalidate verification after credential changes.
- Run connection checks manually and synchronously; remove encryption, connection jobs, health scheduling, and background locks.
- Retain callcenter API behavior unconditionally and remove direct E-Plus connectors, SQL paths, posting helpers, and legacy return repair.
- Preserve API stock, snapshots, history, statuses, customers, sales, returns, offline bills, and token-based retries.
- Clear completed administrator alert references so subsequent failures can create a new alert.
- Reject malformed successful HTTP responses instead of treating invalid JSON as an empty result.
- Restore shared product validation errors after removing connector imports.
- Restore the JSON runtime import used by invoice-address computation so local prepending invoices open normally.
- Route successful sale submission through the branch-owned automatic posting policy and accept only Pending/Saved responses with positive E-Plus serials.
- Poll branch sale lifecycles by original request token, validate forward-only transitions, and retain local records on missing or invalid responses.
- Keep Retry Submission available for retained PrePending bills that already have a branch header ID.
- Correct the one deployed Pending/serial-zero test record back to PrePending with its original token and a retryable branch operation.
- Accept a branch `pending` response without an E-Plus invoice number only when the request explicitly disabled E-Plus pushing.
- Remove the E-Plus submission option from Branch Connections and send no transport choice from callcenter.
- Let the branch create the intermediate `prepending` invoice and automatically run its normal sale submission logic; require a positive E-Plus serial for successful `pending`/`saved` responses.
- Remove the obsolete transport choice from retained submission payloads while preserving their original request tokens and business values.
- Synchronize submitted PrePending and Pending bills through the token-scoped `get_sale_statuses` API with identity, branch-header, serial, and monotonic lifecycle validation.
- Document the paired branch-provider deployment and update the version to 19.0.3.6.1.
- Replace three obsolete direct-SQL test assertions with API-only branch selection, balance-cache, and sales-history coverage.
- Add a regression for opening an invoice form and parsing its customer address datalist.
- Revalidate installation, targeted upgrades, mocked automatic branch submission, status transitions, Arabic runtime output, and PO formats in isolated databases.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/data/branch_connection_jobs.xml`
- `ab_sales/data/ir_cron.xml`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_customer_replication_from_bconnect.txt`
- `ab_sales/models/ab_product_inherit.py`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_inventory.py`
- `ab_sales/models/ab_sales_line.py`
- `ab_sales/models/ab_sales_per_day.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/ab_sales_pos_balance_refresh.py`
- `ab_sales/models/ab_sales_pos_customer.py`
- `ab_sales/models/ab_sales_return_header.py`
- `ab_sales/models/ab_sales_return_header_replication_trans_inherit.py`
- `ab_sales/models/ab_sales_return_line.py`
- `ab_sales/models/ab_sales_return_router.py`
- `ab_sales/models/ab_sales_return_uom_repair.py`
- `ab_sales/models/ab_sales_ui_store_status.py`
- `ab_sales/models/access_policy.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_only_connector.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/models/callcenter_origin.py`
- `ab_sales/models/local_bills.py`
- `ab_sales/tests/test_inventory_total_balance.py`
- `ab_sales/tests/test_bill_wizard_product_filter.py`
- `ab_sales/tests/test_sales_per_day.py`
- `ab_sales/views/ab_sales_return_server_action.xml`
- `ab_sales/views/local_bill_views.xml`
- `ab_sales/changelog.d/2026-10-06-api-only-configuration.md`

Validation:

- Python AST parsing, diff checks, warning-free POT export, and both Arabic PO format checks pass.
- The targeted callcenter upgrade completed at 19.0.3.6.1 with the branch connection still Ready and posting-capable.
- Rollback-only ORM tests confirm token-scoped PrePending-to-Pending-to-Saved transitions and reject Pending with serial zero.
- Live read-only HTTPS checks confirm database/store identity, posting capability, and the token-scoped status endpoint.
- English and Arabic runtime cron names differ correctly. Automated validation performed no E-Plus write.
