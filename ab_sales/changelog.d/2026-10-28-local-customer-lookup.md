## c945122d7 - Hossam Elsheikh - 2026-09-16

Original commit subject: ab_sales: enforce API-only access and display branch bills

User-facing changes:
- Routed callcenter customer lookup through the selected branch API.

Files changed:
- ab_sales/models/branch_services.py
- ab_sales/changelog.d/2026-09-16-api-only-callcenter.md

## Current changes before commit:

- Find active callcenter customers by exact mobile, work, or delivery phone before querying the selected branch.
- Keep store authorization and Odoo customer read access checks ahead of the local result; retain the branch fallback for misses.

Files changed:
- ab_sales/models/branch_services.py
- ab_sales/changelog.d/2026-10-28-local-customer-lookup.md
