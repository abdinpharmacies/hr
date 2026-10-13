## f2695dab - hager yasser - 2026-09-09

Original commit subject: ab_sales_contract/FEAT(#19591): Add Bills Contract Column

- Show the contract on the Bills list and maintain its Arabic translations.

Files changed:

- ab_sales_contract/.i18n_before_bill_info/ar.po
- ab_sales_contract/.i18n_before_bill_info/ar_001.po
- ab_sales_contract/changelog.d/2026-08-30-total-after-discount-list-column.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/views/ab_sales_contract_views.xml

Current changes before commit:

- Show Total After Discount directly below Total in POS, independently of customer payable/Net.
- Remove the added Total After Discount row from A4 and 80 mm previews and printed HTML/text receipts; retain the POS row and existing return receipt layouts.
- Include contract, promotion, product, and unit identifiers in draft preview payloads and obtain current totals from server pricing.
- Use saved invoice pricing for submitted previews and preserve promotion pricing when preparing contract receipts after returns.
- Preserve zero totals and additional invoice-discount behavior; retain Arabic POS translations and remove obsolete receipt translation references.

Files changed:

- ab_sales_contract/changelog.d/2026-10-13-pos-discount-total.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/__init__.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

Verification:

- Targeted ab_sales_contract upgrade completed in codex_contract_promo_20261012 with E-Plus connections blocked; Odoo removed both obsolete inherited receipt views through normal upgrade cleanup.
- Four rollback-only Odoo checks passed: row absence in HTML/text for both formats and both payers; additional discounts, zero totals, plain/promotion-only invoices and removed promotions; saved invoice pricing snapshots; obsolete view removal. Existing receipt totals remain correct.
- POS checks passed in both addon asset orders; the POS Total After Discount row and pricing payloads remain intact.
- Both PO catalogs passed msgfmt --check-format; Python syntax and git diff whitespace checks passed.
- No lifecycle hooks, migrations, live E-Plus writes, production upgrade, or physical print jobs.
