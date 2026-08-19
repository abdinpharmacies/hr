## 3db5d59 - emadco88 - 2026-07-28

Original commit subject: INIT commit pos19

User-facing changes:
- Added doctor prescription support to sales and POS workflows.
- Added doctor and doctor prescription product configuration screens.
- Added POS prescription mode with doctor selection, doctor product badges, and Rx line flags.
- Added backend validation and synchronization for doctor prescription products after bill submission.

Files changed:
- ab_sales_doctor/__init__.py
- ab_sales_doctor/__manifest__.py
- ab_sales_doctor/data/ab_doctor_cron.xml
- ab_sales_doctor/models/__init__.py
- ab_sales_doctor/models/ab_doctor.py
- ab_sales_doctor/models/ab_product_doctor_prescription.py
- ab_sales_doctor/models/ab_sales_header.py
- ab_sales_doctor/models/ab_sales_line.py
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/models/ab_sales_ui_api.py
- ab_sales_doctor/security/ir.model.access.csv
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
- ab_sales_doctor/static/src/pos/pos_action_doctor.scss
- ab_sales_doctor/static/src/pos/pos_action_doctor.xml
- ab_sales_doctor/tests/__init__.py
- ab_sales_doctor/tests/test_doctor_prescription.py
- ab_sales_doctor/views/ab_doctor_views.xml
- ab_sales_doctor/views/ab_product_doctor_prescription_views.xml
- ab_sales_doctor/views/ab_sales_header_views.xml
- ab_sales_doctor/views/ab_sales_line_views.xml
- ab_sales_doctor/views/menus.xml

## Current changes before commit

User-facing changes:
- Display doctors as code, name, and specialty joined with ` - ` wherever `ab_doctor.display_name` is rendered.
- Allow doctor lookup by code, name, and specialty through the backend display name search used by many2one selectors.
- Added Arabic translations for doctor, prescription, POS doctor dialog, validation, and doctor product labels.
- Merged Arabic translations with exported POT references so Odoo can apply field and view labels correctly.
- Wrapped POS doctor notification strings for translation.
- Exposed the translation helper to doctor POS OWL templates so translated labels do not crash rendering.
- Moved the POS doctor placeholder translation through JavaScript so `Doctor...` switches correctly by user language.
- Added tests for full doctor labels, missing label parts, code search, and specialty search.

Files changed:
- ab_sales_doctor/models/ab_doctor.py
- ab_sales_doctor/tests/test_doctor_prescription.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
- ab_sales_doctor/static/src/pos/pos_action_doctor.xml
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/changelog.d/2026-08-19-doctor-code-display-search.md
