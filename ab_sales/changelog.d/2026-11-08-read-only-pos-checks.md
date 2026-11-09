Recent relevant commit:

- Commit: c8acd5692a0d78543f7748edd2a73e357958055f
- Author: Hossam Elsheikh
- Date: 2026-11-05T16:45:11+02:00
- Original subject: feat(ab_sales): support native branch bills, returns, and central inventory status
- Added native branch bill/return and central inventory support.

Files changed:

- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-11-05-role-split.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/bill_return_status.py
- ab_sales/models/central_inventory_client.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/views/local_bill_views.xml
- ab_sales/workflow.md

Current changes before commit:

- Return live branch balances and timestamps without saving inventory rows or locking branch cache coordination rows.
- Use live default prices in product details without relying on cache persistence.
- Return popup refresh results directly; preserve scheduled cache writers and unavailable fallback behavior.

Files changed:

- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-11-08-read-only-pos-checks.md
- ab_sales/models/ab_product_balance_wizard.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/branch_services.py

Validation:

- Isolated local database: focused read-only validation, live balances/prices, fallback, and audit attribution checks passed.
- Six concurrent clients / 54 operations: no protected-table SQL writes; search p95 0.304 seconds with mocked branch API responses.
- Headless Chromium harness: heartbeat overlap/cleanup, stale response ordering, zero balance and offline retention passed.
- Targeted module upgrade completed; existing regression suite had 42 replication-policy fixture errors, identical on unchanged HEAD.
- No new user-facing strings; existing Arabic translations retained. Production was not upgraded.
