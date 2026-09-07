Recent relevant commit:

- Commit: `421e10dd5fea111dd0a4a43e57a3385aee894d8f`
- Author: ahmedzenhom2610
- Date: 2026-08-03
- Original subject: ab_sales_promo_report/ UPD show new fields
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_sales_promo_report/i18n/ar_001.po
  - ab_sales_promo_report/models/ab_sales_promo_report.py
  - ab_sales_promo_report/tests/test_sales_promo_report.py
  - ab_sales_promo_report/views/ab_sales_promo_report_views.xml

Current changes before commit:

- User-facing changes:
  - Removed the shared passive mirror mixin from sales promo report lines because report-generated artifacts are outside the updated high-value passive list.
- Files changed:
  - ab_sales_promo_report/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_promo_report/models/ab_sales_promo_report.py
