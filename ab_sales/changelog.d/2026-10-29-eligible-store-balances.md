## c08f019c1f82391c2c984bae8421af83d7bb748c - Alhassan Hossny - 2026-10-28

Original commit subject: ab_sales/feat: enforce POS store scope across sales workflows

- Bound scheduled all-store balance reads to 120 seconds while retaining the two-second live-query limit.
- Preserve saved balances when the central stock query fails or times out.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-27-central-transfer-balances.md
- ab_sales/changelog.d/2026-10-28-unified-pos-store-permissions.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_per_day.py
- ab_sales/models/ab_sales_per_day_sync_wizard.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/branch_services.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_barcode_link.js

## Current changes before commit:

- Include only active, transfer-enabled stores in all-store balance popup rows, live queries, cached totals and scheduled/manual all-store refreshes, even with `active_test=False`.
- Reject individual popup refresh requests for excluded stores through the shared eligibility selector; retain their existing cached records.
- Document eligibility and cache retention in the branch API workflow. No public API, schema or user-facing string changes.

Files changed:
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/changelog.d/2026-10-29-eligible-store-balances.md

Validation:
- Passed 30 focused checks using actual backend methods and Odoo Domain objects with mocked ORM records, external queries and cache writes, under both normal active filtering and `active_test=False`.
- Covered all four eligibility combinations, popup rows, cached totals, live query IDs, cached fallback, excluded-store refresh rejection, missing E-Plus IDs, scheduled/manual full and product-specific refreshes, retained cache records and an empty eligible set.
- Python AST parsing and `git diff --check` passed. Reviewed the code diff: no user-facing strings changed, so neither Arabic catalog requires an update.
- Harness: `/tmp/check_sales_store_eligibility.py` (outside the addon package). No database upgrade, production restart or external database write was performed; runtime ORM/database integration was not exercised.
