## 1b3b207f - hager yasser - 2026-10-15

Original commit subject: ab_sales_contract/FEAT(#21055): Enforce Allowed Customers for Promotions(part2)

- Carry selected customer context through contract POS and draft-print promotion pricing.
- Reject stale promotion responses after customer changes while preserving historical invoice pricing.

Files changed:

- ab_sales_contract/changelog.d/2026-10-15-promotion-customer-context.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

Current changes before commit:

- Allow otherwise eligible contracts to enable promotions with a nonzero Max Bill Value and to change the cap while promotions remain enabled.
- Remove Max Bill Value from the promotion constraint's watched fields and rejection condition; preserve the default-discount, product-discount, fixed-copay, and percentage requirements.
- Remove the zero-bill-cap requirement from the English validation message and append the revised Arabic translation to both language catalogs, preserving existing entries.

Files changed:

- ab_sales_contract/changelog.d/2026-10-15-promotion-bill-cap.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/ab_contract.py

Verification:

- Reviewed the original constraint commit b28b327a and the current module diff; invoice calculations, bill-cap pricing, POS, returns, security, and public APIs are unchanged.
- Exported the module POT from Odoo 19 before appending the new Arabic entries; both PO files pass msgfmt --check-format and preserve every existing translation.
- Upgraded only ab_sales_contract successfully in isolated database codex_promo_customers_20261015.
- Passed 49 grouped rollback-only runtime checks: positive and zero caps for both supported copays, changing caps, enabling existing contracts, multi-record updates, all six invalid default discounts, product-specific discounts, fixed copays, unsupported percentages, and exact English/ar_001 validation messages.
- Python syntax and static constraint checks passed; verification scripts remain in /tmp, outside the production addon package. E-Plus connections were blocked during validation and all verification fixtures were rolled back.
