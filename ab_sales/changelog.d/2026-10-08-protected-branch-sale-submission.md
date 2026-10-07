# ab_sales: protected callcenter sale submission

## Recent commit

Commit: `d1ec5aa24525bb2415c5ed51d5b5b0f3f491c438`

Author: Alhassan Hossny

Date: 2026-10-07T15:08:04+03:00

Original commit subject: ab_sales/Update: make callcenter sales integration API-only

- Made the callcenter sales integration API-only while preserving local bills and token-based recovery.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-10-06-api-only-configuration.md`
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
- `ab_sales/tests/test_bill_wizard_product_filter.py`
- `ab_sales/tests/test_inventory_total_balance.py`
- `ab_sales/tests/test_sales_per_day.py`
- `ab_sales/views/ab_sales_branch_rpc_config_views.xml`
- `ab_sales/views/ab_sales_return_server_action.xml`
- `ab_sales/views/local_bill_views.xml`

## Current changes before commit:

- Commit Unknown, original token, request revision, exact wire payload and pinned branch identity before outbound HTTP.
- Keep generic failures and invalid responses Unknown; require confirmed Pending/Saved with positive IDs before reporting success.
- Block header/line edits and identity changes while unresolved or accepted; permit rejected business corrections at the next revision.
- Preserve original data on Unknown retries, clear removed promotions on corrected local bills and log actual outcome/revision.
- Protect submission across commits and detect concurrent line edits through parent version changes.
- Keep unresolved POS cache entries, show Retry and diagnostics, refresh on reload/focus/cache events and ignore stale status responses.
- Guard existing promotion/contract frontend callbacks inside ab_sales without changing those modules; preserve employee session checks.
- Expose Unknown/Rejected in bill search, local forms and Arabic UI; add rollout documentation and version 19.0.3.7.0.
- Keep callcenter API-only, with no B-Connect dependency; preserve return/customer recovery.
- Document administrator API-key support in branch ab_branch_api 19.0.5.5.1; retain callcenter credential-management and connection-test permissions.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-10-08-protected-branch-sale-submission.md`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_callcenter_rpc_log.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/local_bills.py`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.xml`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`
- `ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js`
- `ab_sales/views/ab_sales_callcenter_rpc_log_views.xml`
- `ab_sales/views/local_bill_views.xml`

Validation:

- Targeted isolated module installs/upgrades, Python/XML/JS syntax and diff checks.
- Actual ORM guard, revision, rejected correction, concurrency, branch identity and pricing tests with fake external SQL.
- Two isolated Odoo registries over the actual JSON-2 client: lost HTTP/external commit acknowledgements, rejection/correction and original-payload retries.
- Real OWL browser mount with unchanged promotion, contract and employee patches; UI locks, delayed pricing callbacks, focus refresh and listener cleanup.
- Arabic PO format checks and runtime ar_001 status/view translations.
- No production database changes, real E-Plus writes, production restarts or commits.

Validation limit: installing the existing employee-access sales module on a clean callcenter database pulls ab_sales_cashier, which inherits an unavailable ab_eplus_connect model. This pre-existing dependency is outside the two-module change; core sales/promo/contract install and employee frontend checks passed.
