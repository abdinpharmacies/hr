## f2a95858a28cae17d4f99c901f00d24a5b6b7424 — hager yasser — 2026-10-15

Original commit subject: ab_sales_contract/FIX(#21079): Contract promotions: manual selection in POS

User-facing changes:
- Support manual contract-promotion selection in POS.

Files changed:
- ab_sales_contract/changelog.d/2026-10-15-pos-manual-promotions.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

## Current changes before commit:

- Explicitly allow contract selection and total invoice discount through the shared POS header filter.

Files changed:
- ab_sales_contract/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
