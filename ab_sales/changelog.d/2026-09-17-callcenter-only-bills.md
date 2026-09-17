# ab_sales: call-center-only bills

## Recent commit

Commit: `c945122d71abe2cf365fef90a5ceee5266e2c3c9`

Author: Hossam Elsheikh

Date: 2026-09-16T15:46:17+03:00

Original commit subject: ab_sales: enforce API-only access and display branch bills

- Route call-center services through the branch API and browse branch bills.

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

- Require the callcenter_only provider capability before bill/return requests and when reusing cached pages; show clear upgrade errors and invalidate old search sessions.
- Add protected origin fields and read-only forms; stamp trusted local POS, return-action, and new return-form creation while copies and old records remain unmarked.
- Clear stale displayed bills/details after rejected searches and retain partial results from available branches.
- Preserve the existing uncommitted status-refresh implementation: poll successful unresolved submission logs in scoped batches, validate identities, preserve failures, and never replay submissions.
- Maintain both Arabic translation files and document branch-first rollout and all-operator visibility within authorized branches.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-17-callcenter-only-bills.md`
- `ab_sales/changelog.d/2026-09-17-callcenter-order-status.md`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/models/callcenter_origin.py`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/views/ab_sales_branch_api_views.xml`

Validation: targeted upgrades on isolated database copies; real ORM origin/access/filter/pagination and print checks; mocked transport and external SQL; status-refresh and retry regressions; Arabic runtime checks; PO format, Python/XML/JS syntax, and diff checks. Test scripts and results are outside the addons at `/tmp/callcenter_origin_validation`. No production database upgrade or external database writes.
