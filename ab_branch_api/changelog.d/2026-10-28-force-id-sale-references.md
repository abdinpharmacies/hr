## 0d0802f09 - Hossam Elsheikh - 2026-10-26

Original commit subject: ab_branch_api/preserve optional sale fields as protected typed metadata

User-facing changes:
- Preserve optional sale fields as typed branch metadata while validating supported relations.

Files changed:
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/sale_metadata.py

## Current changes before commit:

- Resolve replicated sale products, contracts, employees, doctors, and promotions by their force IDs while preserving legacy references and customer E-Plus synchronization.
- Reject mismatched ID references in sale metadata and promotions that the branch cannot apply.
- No new user-facing strings; existing English and Arabic translations remain valid.

Files changed:
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/sale_metadata.py
- ab_branch_api/changelog.d/2026-10-28-force-id-sale-references.md
