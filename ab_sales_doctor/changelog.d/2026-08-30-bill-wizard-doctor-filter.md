## af11be7 - emadco88 - 2026-08-30

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

## Current changes before commit

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
