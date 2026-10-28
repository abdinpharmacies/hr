## 774916288 - emadco88 - 2026-10-28

Original commit subject: ab_sales/ FIX customer lookup

User-facing changes:
- Look up active callcenter customers by phone before requesting a branch customer.

Files changed:
- ab_sales/models/branch_services.py
- ab_sales/changelog.d/2026-10-28-local-customer-lookup.md

## Current changes before commit:

- Activate a callcenter spare only after the selected branch confirms the same converted, active customer and phone.
- Continue to block unrelated archived customers and branch or customer mismatches.
- Record a new customer Create request as successful only after the callcenter customer import succeeds.
- Send force-ID references for replicated products, contracts, employees, doctors, and promotions while retaining E-Plus customer references.
- Allow return employee references to use their replicated ID while still requiring an active employee and cost center.
- No new user-facing strings; existing English and Arabic translations remain valid.

Files changed:
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/branch_services.py
- ab_sales/changelog.d/2026-10-28-converted-spare-callcenter.md
