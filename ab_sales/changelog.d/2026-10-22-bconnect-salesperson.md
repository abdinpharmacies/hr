## 13917dabcb39987ee42689f82b7b36852c73ca39 — emadco88 — 2026-10-22

Original commit subject: ab_sales/ UPD allowed fields hook

User-facing changes:
- Introduce extendable POS header and line allowlists.

Files changed:
- ab_sales/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js

## Current changes before commit:

- Use the selected Actual Salesperson for B-Connect invoice `emp_id` and header, line, and delivery `sec_insert_uid` values.
- Keep the logged-in employee in Odoo's existing POS HR audit fields and operation logs.
- Fall back to the logged-in employee only when no salesperson is selected; reject a selected employee without an E-Plus mapping.
- Leave previously submitted B-Connect invoices unchanged and preserve the existing recovery path.

Files changed:
- ab_sales/changelog.d/2026-10-22-bconnect-salesperson.md
- ab_sales/models/ab_sales_header.py
