
## 30f98ab440b57dcfb3ff448306dace7890cd1b2e

Author: emadco88
Date: 2026-10-29T10:14:56+03:00
Subject: ab_branch_api/ UPD remove is_callcenter restriction

- Recent module baseline reviewed before source-identity work.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-29-legacy-pos-invoice-returns.md
- ab_branch_api/models/branch_api.py

## Current changes before commit:

- Fix fresh branch POS promotion previews: use an empty JSON default callable and consult protected origin only on persisted original invoices. Existing-invoice previews retain origin; fresh previews cannot inject it.

- Accept dynamic positive source serials from bearer-authenticated Call Center users when exactly one active source replica exists; no hardcoded serial or per-user serial/UUID binding.
- Keep UUID as optional validated metadata, and distinguish absent source (local eligibility) from invalid source (rejection) on sales and returns.
- Preserve protected header origin, submitted-promotion binding, operation payloads, hashes, and destination routing.
- Remove the interim source-user fields and settings view through normal module upgrade.
- Add actionable authorization/validation errors in English and both Arabic translation files.
- Preserve legacy local eligibility and existing retry/reconciliation behavior.

Files changed:
- ab_branch_api/__manifest__.py
- ab_branch_api/models/__init__.py
- ab_branch_api/models/source_identity.py
- ab_branch_api/models/sale_metadata.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/guarded_sales.py
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/changelog.d/2026-10-29-submission-source-identity.md

Verification:
- Fresh isolated installation and upgrade from the interim user-binding implementation passed.
- Fifteen focused checks plus invalid/unauthorized cases passed with network access blocked and test fixture changes rolled back. Coverage includes two dynamic serials, nonmember administrator rejection, inactive/invalid sources, optional UUIDs, sale/return fallback, removed fields/view, promotion identity, and duplication.
- POT export and msgfmt format checks completed for both Arabic files; Arabic runtime authorization errors and the operations action were verified.
- Targeted receiver upgrade completed on abdin_old_pos19. The existing admin credential owner was granted the Call Center role through a one-time, explicitly authorized security XML import, not distributed module installation data.
- No E-Plus writes or bill replay performed.
- Restarted the local receiver and signaled the role cache change. Live configured bearer credential passed connection verification and callcenter-role authorization; a deliberately invalid source was rejected before any business operation. Login returned HTTP 200.
- Preview regression: product 74542 (صنف مؤقت) returns promotions 479, 480, and 482 in both allowed stores 104 and 135, with external network blocked. Existing invoice origin and forged unsaved metadata cases covered.
