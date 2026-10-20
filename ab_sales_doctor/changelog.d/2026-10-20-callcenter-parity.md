Commit: af11be7ec75e844d6b383462d3289342dc519664
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date: 2026-08-23T15:52:32+03:00
Subject: ab_sales_doctor/fix(#2174): create main doctors by unique code only

User-facing changes:
- Create main doctors by their unique code.

Files changed:
- ab_sales_doctor/changelog.d/2026-08-19-doctor-code-display-search.md
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/models/ab_doctor.py
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
- ab_sales_doctor/static/src/pos/pos_action_doctor.xml
- ab_sales_doctor/tests/test_doctor_prescription.py

Current changes before commit:
- Add doctor filters to local bill search and retain prescription flags in the POS.
- Maintain both Arabic catalogs.

Files changed:
- ab_sales_doctor/__manifest__.py
- ab_sales_doctor/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/models/ab_sales_ui_api.py
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.js
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.scss
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.xml
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
