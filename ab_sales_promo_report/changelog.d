commit 421e10dd5fea111dd0a4a43e57a3385aee894d8f
Author: ahmedzenhom2610 <113896212+ahmedzenhom2610@users.noreply.github.com>
Date: 2026-08-03
Subject: ab_sales_promo_report/ UPD show new fields

User-facing changes:
- Show added sales promotion report columns for compensation and approval context.

Files changed:
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/tests/test_sales_promo_report.py
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml

Current changes before commit:
- Add Promotion Ownership as a readonly related report-line field from the matched promotion.
- Show Promotion Ownership immediately after Promo in the sales promotion report list view.
- Add Arabic translations for Promotion Ownership and its selection labels.
- Allow system administrators to access the sales promo report lines and load wizard.

Files changed:
- ab_sales_promo_report/changelog.d
- ab_sales_promo_report/i18n/ar.po
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/security/ir.model.access.csv
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml
