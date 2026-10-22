## 370c33c3d90acba569dae8a79c4bbe73cb0b5ea9 — emadco88 — 2026-10-22

Original commit subject: ab_sales/ FIX actual sales person

User-facing changes:
- Use the selected Actual Salesperson for B-Connect invoice attribution while retaining Odoo employee audit details.

Files changed:
- ab_sales/changelog.d/2026-10-22-bconnect-salesperson.md
- ab_sales/models/ab_sales_header.py

## Current changes before commit:

- Preserve the original invoice salesperson when posting partial or full sales returns.
- Continue recording the return employee in return records and the original invoice's update audit field.
- Keep existing invoice creation identity, return amounts, quantities, and historical records unchanged.

Files changed:
- ab_sales/changelog.d/2026-10-22-return-salesperson.md
- ab_sales/models/ab_sales_return_header.py
