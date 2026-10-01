## af11be7 - Mohamed Fawzy - 2026-08-23

Original commit subject: ab_sales_doctor/fix(#2174): create main doctors by unique code only

User-facing changes:
- Kept POS doctor creation create-only by doctor code.
- Preserved doctor code display and search behavior for POS doctor workflows.
- Maintained validation coverage around doctor code uniqueness and prescription flows.

Files changed:
- ab_sales_doctor/changelog.d/2026-08-19-doctor-code-display-search.md
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/models/ab_doctor.py
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
- ab_sales_doctor/static/src/pos/pos_action_doctor.xml
- ab_sales_doctor/tests/test_doctor_prescription.py

## b476c59 - hager yasser - 2026-08-30

Original commit subject: ab_sales_doctor/FEAT(#2418): Add doctor and item-type filters(Part2)

User-facing changes:
- Added the Bill Wizard doctor multi-select filter from `ab_sales_doctor`.
- Reused doctor display-name search so the selector searches doctor code, name, and specialty, including archived doctors through `active_test=False`.
- Sent selected doctor IDs to the Bill Wizard search RPC and cleared them on Reset.
- Passed the POS product item-type mode into doctor prescription product results.
- Added scoped Bill Wizard doctor filter styles to prevent selected doctor tags from overflowing.

Files changed:
- ab_sales_doctor/changelog.d/2026-08-30-bill-wizard-doctor-filter.md
- ab_sales_doctor/models/ab_sales_ui_api.py
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.js
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.scss
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.xml
- ab_sales_doctor/static/src/pos/pos_action_doctor.js

## Current changes before commit:

User-facing changes:
- Apply the POS minimum/exact and maximum/range price criteria to prescription recommendations using the shared Sales decimal helpers and product master default price.
- Apply balance and current-store balance eligibility before limiting price-filtered prescription results; preserve existing behavior when both price inputs are empty.
- Pass raw price strings and balance criteria from POS, and discard delayed prescription results after search criteria change.
- Reuse translated validation messages from ab_sales; no new user-facing strings, price display changes, dependencies, or posting changes.

Validation:
- Installed the doctor extension in the isolated POS test database.
- Added backend checks for exact/range, name/code intersection, item type, branch balance, invalid inputs, and empty-filter compatibility outside the production addon.
- Executable frontend checks verify forwarded price criteria and stale prescription response rejection.
- Combined backend suite: 50/51 passed. The existing generic-user doctor-creation ACL test fails identically on unchanged HEAD; no security changes were made.
- Combined POS assets compile successfully; both Arabic catalogs pass format checks. Browser-based visual verification remains unavailable.

Files changed:
- ab_sales_doctor/changelog.d/2026-08-30-bill-wizard-doctor-filter.md
- ab_sales_doctor/models/ab_sales_ui_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
