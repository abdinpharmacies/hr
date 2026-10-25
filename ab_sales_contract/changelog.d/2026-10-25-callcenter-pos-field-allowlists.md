## fd34fb6d994f7cbe5b54395fdbb2d159ee29647b — hossam elsheikh — 2026-10-21

Original commit subject: ab_sales_contract:fix_correction_preview_and_translation

User-facing changes:
- Preserve contract correction previews and complete their Arabic translations.

Files changed:
- ab_sales_contract/__manifest__.py
- ab_sales_contract/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_contract/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js

## Source reference: 9110256a20d38ed581de186a13847360b0201eff — emadco88 — 2026-10-22

Original commit subject: ab_sales_contract/ UPD add the allowed fields via hook

User-facing changes:
- Preserve contract selection and invoice discount through submission.

Files changed:
- ab_sales_contract/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py

Adapted to the callcenter branch API workflow; not a whole-branch merge.

## Current changes before commit:

- Allow contract_id and total_invoice_discount through shared submission filters while retaining existing pricing and correction validation.

Files changed:
- ab_sales_contract/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales_contract/models/ab_sales_pos_api_contract.py
