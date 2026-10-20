Commit: 421e10dd5fea111dd0a4a43e57a3385aee894d8f
Author: ahmedzenhom2610 <113896212+ahmedzenhom2610@users.noreply.github.com>
Date: 2026-08-03T11:20:09+03:00
Subject: ab_sales_promo_report/ UPD show new fields

User-facing changes:
- Display promotion compensation metadata in the earlier report.

Files changed:
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/tests/test_sales_promo_report.py
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml

Current changes before commit:
- Replace external SQL report reads with authorized saved local callcenter invoices.
- Report frozen invoice promotion totals with branch/date/product/promotion filters and user-owned report rows.
- Keep repeated invoice totals non-additive and omit inferred compensation settlement.
- Maintain both Arabic catalogs.

Files changed:
- ab_sales_promo_report/__manifest__.py
- ab_sales_promo_report/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales_promo_report/i18n/ar.po
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/security/ir.model.access.csv
- ab_sales_promo_report/security/record_rules.xml
- ab_sales_promo_report/security/security_groups.xml
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml
- ab_sales_promo_report/views/menus.xml
