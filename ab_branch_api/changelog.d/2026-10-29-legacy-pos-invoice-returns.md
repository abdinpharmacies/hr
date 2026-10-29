## 263a749d529cfcfda82739034c8fada04a904591 - emadco88 - 2026-10-28

Original commit subject: ab_branch_api/ FIX api use force-ids instead of unknown

- Resolve selected sales references using their shared record IDs.

Files changed:
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/sale_metadata.py
- ab_branch_api/changelog.d/2026-10-28-force-id-sale-references.md

## Current changes before commit:

- Allow legacy POS invoices to enter the return flow without a local sales header marked as a call-center order.
- Use the existing committed E-Plus invoice/store validation before creating the return; preserve return identity checks, employee authorization, return-window and quantity validation, and posting/retry safeguards.
- Reject nonpositive invoice numbers using the existing translated request-mismatch message; preserve historical invoice markers and translation entries.
- Bump the module version to 19.0.5.5.7.

Files changed:
- ab_branch_api/models/branch_api.py
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-29-legacy-pos-invoice-returns.md

Validation:
- Passed isolated checks of the actual return-header method with mocked ORM/backend boundaries: no local source header required, nonpositive/missing/wrong-branch rejection, existing return reuse, and mismatched return identity rejection.
- Confirmed load/submit, operation token, line-selection, and employee-validation method bodies are unchanged from HEAD.
- Passed both Arabic catalog format checks and whitespace checks. Reused existing translated wording; no new translation entries required.
- No real E-Plus reads/writes, full end-to-end posting test, database upgrade, or deployment was performed.
