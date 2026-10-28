## 9f7c5e97b - Hossam Elsheikh - 2026-10-15

Original commit subject: ab_sales/Added five backend helper files in ab_sales.

User-facing changes:
- Added branch-scoped customer import and archive protection for POS backend requests.

Files changed:
- ab_sales/models/ab_sales_pos_backend.py

## Current changes before commit:

- Allow an archived branch spare to be activated after verifying its converted, active E-Plus customer and matching branch, ID, code, and phone.
- Keep unrelated archived customers blocked and leave existing uncertain customer operations untouched.
- No new user-facing strings; existing English and Arabic translations remain valid.

Files changed:
- ab_sales/models/ab_sales_pos_backend.py
- ab_sales/changelog.d/2026-10-28-converted-spare-customer.md
