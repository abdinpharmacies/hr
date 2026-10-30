## f9aaae6f707e21d813dce02b554c68d3f4b136a7 - Alhassan Hossny - 2026-10-29

Original commit subject: ab_sales/fix: preserve selected customer identity in branch submissions

User-facing changes:
- Preserve the selected customer's identity and customer snapshot in branch submissions and invoice responses.

Files changed (relevant to this fix):
- ab_sales/models/ab_sales_pos_api.py

## Current changes before commit:

- Load fresh selected-branch stock before creating POS submission lines, so a valid batch price displayed in the badges is available to the selling-price constraint.
- Prepare temporary lines together and reuse the branch stock adapter's store grouping and bounded product batches.
- Replace any supplied inventory with server-derived rows; retain default-price, unpriced-product, unit conversion, branch identity, and product identity validation.
- Propagate failed branch reads instead of validating against missing inventory; preserve duplicate-token replay without refreshing or changing existing lines.
- No new or updated user-facing strings; both Arabic translation files remain applicable without changes.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/changelog.d/2026-10-30-submit-branch-price-validation.md

Validation:
- Passed registry-loaded submission preparation and ORM constraints using mocked branch stock: prices 1.00/1.50, rejected 1.25 and forged browser inventory, alternate units, multi-line batching, duplicate-token replay, unpriced products, successful empty stock, and branch-read failure rollback.
- Test master-record policy was mocked only in the isolated test process; all database fixtures were rolled back. No branch sales were sent.
- Passed isolated checks of the real stock adapter for database/store/product mismatch rejection and 200-product request batching.
- Targeted ab_sales upgrade on local callcenter19 completed successfully with HTTP and cron disabled; no base upgrade.
- Regression scripts remain outside the addon: /tmp/test_callcenter_submit_prices.py and /tmp/test_callcenter_stock_validation.py.
- The existing long-running Odoo process needs a Python restart to load the changed method; the upgrade and checks used separate processes.
