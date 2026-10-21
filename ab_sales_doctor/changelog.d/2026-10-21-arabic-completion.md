Commit: a14708ebd65b37fea23e10c9adb3c874b6ee307d
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:34:37+03:00
Subject: ab_sales_doctor/feat: add doctor filters to local callcenter bill search

User-facing changes:
- Add doctor filters to local callcenter bill searches.

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

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.

Files changed:
- ab_sales_doctor/__manifest__.py
- ab_sales_doctor/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.xml
