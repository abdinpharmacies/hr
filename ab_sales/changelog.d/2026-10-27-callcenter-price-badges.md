## 18a2395c29e9bb80e539a35277ae9b6fa27f5124 - emadco88 - 2026-10-27

Original commit subject: ab_sales/ FIX show price tags

Source branch: pos19. Adapted below to the callcenter branch API architecture.

User-facing changes:
- Refresh invoice price and quantity badges with inventory balances while preserving cashier selections.
- Ignore outdated refresh responses and exclude inventory display changes from draft revisions.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/changelog.d/2026-10-27-refresh-price-badges.md

## Current changes before commit:

- Refresh invoice-line inventory and price badges through existing `_balances` and `_stock` branch API methods, for both automatic and manual refresh.
- Preserve existing numeric API responses, scoped multi-branch search totals, cashier selling prices and quantities, and unit conversion rules.
- Preserve badges on RPC failure; replace depleted batch badges after successful empty-stock responses, retaining the default-price badge.
- Reject obsolete browser responses and omit stock details if the cached balance timestamp changes during the stock request. The existing stock API does not expose a snapshot timestamp; no provider change is required.
- Exclude inventory JSON from browser and server draft comparisons.
- Reuse branch/database/product validation and existing bounded API batches. No new SQL or external database writes.
- No new or changed user-facing strings; existing Arabic translations in both language files remain applicable.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/branch_services.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/changelog.d/2026-10-27-callcenter-price-badges.md

Validation:
- Passed isolated Python checks against production methods for API metadata, numeric compatibility, totals, empty inventory, access denial, cross-branch/database/product rejection, RPC failures, changed-cache protection, unpriced products, batching, and draft comparisons.
- Passed executable JavaScript checks for automatic/manual refresh, preserved cashier selections, single unit conversion, failures, empty stock, removed lines, changed branch/bill/product/request, overlapping responses, draft fingerprints, and multi-branch search totals.
- Passed Python AST parsing, JavaScript syntax checks, and git diff whitespace checks.
- Targeted `ab_sales` upgrade on local `callcenter19` exited successfully using isolated ports 5069/5072 with HTTP and cron disabled. Registry-loaded runtime checks passed for API override resolution, badge grouping, empty stock, unpriced products, and draft comparisons.
- Upgrade log also reports missing/unloaded `ab_users` and inconsistent `ab_sales_cashier` dependencies outside this change. These were not modified.
- No live branch requests or browser interaction were used in verification. Development scripts are outside the addon in `/tmp/test_callcenter_refresh_badges.py`, `/tmp/test_callcenter_refresh_badges.mjs`, and `/tmp/check_callcenter_badges_runtime.py`.
