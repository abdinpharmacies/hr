## b28b327a - hager yasser - 2026-10-13

Original commit subject: ab_sales_contract/FEAT(#20897): Contract-controlled promotions with a single payer

- Add contract-controlled promotions with a single payer and server-calculated POS and print totals.
- Preserve submitted invoice pricing and promotion-aware return calculations.

Files changed:

- ab_sales_contract/changelog.d/2026-08-30-total-after-discount-list-column.md
- ab_sales_contract/changelog.d/2026-10-12-contract-promotions.md
- ab_sales_contract/changelog.d/2026-10-13-pos-discount-total.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/__init__.py
- ab_sales_contract/models/ab_contract.py
- ab_sales_contract/models/ab_contract_product_origin.py
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_line_inherit.py
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_return_header_inherit.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
- ab_sales_contract/views/ab_sales_contract_views.xml

Current changes before commit:

- Pass the selected customer through the optional customer_id argument of contract pricing and into promotion evaluation.
- Include customer identity in contract POS requests and response checks so stale responses cannot restore another customer's promotion.
- Include customer context in draft print payloads and ordinary or contract promotion pricing; new-customer mode has no selected existing customer.
- Carry the source customer into temporary contract print headers while preserving saved invoice rendering and historical promotion repricing.

Files changed:

- ab_sales_contract/changelog.d/2026-10-15-promotion-customer-context.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

Verification:

- Targeted ab_sales_contract and ab_sales_promo upgrades passed in isolated database codex_promo_customers_20261015.
- Fourteen grouped rollback-only Odoo checks passed, including the original nine customer-promotion checks, both contract payer types, both draft print formats, temporary print headers, and saved invoice rendering.
- Twelve contract POS checks passed across both addon asset load orders; the original eight ordinary POS checks also passed.
- A fresh ab_sales_contract install without ab_sales_promo and three rollback-only compatibility checks passed in codex_promo_customer_nopromo_20261015.
- The unchanged 17-test regression suite reports three failures, five errors, and five skips. The same eight failure/error identities and five skips reproduce against the pre-change contract code. Existing return tests use outdated methods or fixtures; specific-product fixtures omit required compensation_company_id; marker tests require existing product data.
- Python and JavaScript syntax and git diff whitespace checks passed. No user-facing strings were added or changed, so existing Arabic translations remain unchanged.
- E-Plus connections were blocked during validation. Development scripts and fixtures remain outside addon packages; no production upgrade or physical print jobs were performed.
