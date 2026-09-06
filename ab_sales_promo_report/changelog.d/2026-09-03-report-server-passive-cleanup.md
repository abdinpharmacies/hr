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
  - Added passive sync metadata inheritance for classified high-value report facts where applicable.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_sales_promo_report/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales_promo_report/__manifest__.py
  - ab_sales_promo_report/models/ab_sales_promo_report.py
