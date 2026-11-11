# Contract-controlled promotions — 2026-10-12

Current changes before commit:

- Add Allow Promotions, defaulting to off, with strict eligibility checks for six default discounts, product rules, copay, and bill cap.
- Apply promotion savings to the sole payer before existing additional invoice-discount logic, retaining contract identity and submitted pricing-mode/payer snapshots.
- Keep backend pricing, POS previews, submission output, and branch-scoped partial/full returns aligned, including the company balance.
- Preserve zero customer liability during contract return repricing instead of falling back to the gross discounted total.
- Refresh the contract return regression fixtures for the current return quantity and pricing APIs.
- Add English source labels and Arabic translations for both language codes.

Files changed:

- ab_sales_contract/changelog.d/2026-08-30-total-after-discount-list-column.md
- ab_sales_contract/changelog.d/2026-10-12-contract-promotions.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/ab_contract.py
- ab_sales_contract/models/ab_contract_product_origin.py
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_line_inherit.py
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_return_header_inherit.py
- ab_sales_contract/tests/test_ab_sales_return_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
- ab_sales_contract/views/ab_sales_contract_views.xml

Verification:

- Isolated Odoo install and targeted upgrade; 13 rollback-only feature checks with external connections blocked and posting cursors mocked.
- The combined promotion and contract TransactionCase suite passes all 17 tests.
- POS checks in both asset orders cover payers, selection/removal, cache reload, stale responses, and promotion-only invoices.
- Both Arabic PO files pass msgfmt --check-format; runtime Arabic contract action and Allow Promotions label checked.
- No migrations, lifecycle hooks, historical repricing, or live E-Plus writes. Development checks are kept outside the addon packages.
