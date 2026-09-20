commit 02b72220c94d6533d1b2938324bfc21b7ecc50bc
Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-08-26
Subject: ab_sales_promo_report/FEAT(#2327):  Minimal Promotion Ownership Column

User-facing changes in that commit:
- Add related Promotion Ownership to the report and Arabic translations.
- Grant system administrators access to the report lines and wizard.

Files changed in that commit:
- ab_sales_promo_report/changelog.d
- ab_sales_promo_report/i18n/ar.po
- ab_sales_promo_report/i18n/ar_001.po
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/security/ir.model.access.csv
- ab_sales_promo_report/views/ab_sales_promo_report_views.xml

Current changes before commit:
- Bump 19.0.1.0.0 to 19.0.1.0.1.
- Process contiguous inclusive seven-day report batches with fetchmany(2000), consuming each cursor inside its connection context.
- Normalize raw ODBC fetchmany rows using cursor column names while preserving dictionary rows; cover the connector wrapper contract in a regression test.
- Build values per batch, create at most 1,000 report lines per call, retain created IDs and release batch rows/values.
- Apply replacement once for the complete requested period; preserve existing empty-result messages and total row counts.
- Add report-period overlap filtering while preserving active, company, store, explicit-promotion filters and sequence,id ordering.
- Match each invoice product independently against date-valid promotions and the complete invoice compensation; reuse results for repeated source rows.
- Preserve discount formulas and tolerances, no_promo_applied behavior, and historical out_of_date values; newly generated lines never attach date-invalid promotions.
- Add coverage for batching, boundaries, open-ended dates, product matching, related dates, scope, mapping, SQL filters and tolerance.
- Use installation context only for transactional test fixtures on replica databases; report calls retain their normal context.
- Leave SQL structure, connector code, UI, strings and translations unchanged.

Files changed:
- ab_sales_promo_report/__manifest__.py
- ab_sales_promo_report/models/ab_sales_promo_report.py
- ab_sales_promo_report/tests/test_sales_promo_report.py
- ab_sales_promo_report/changelog.d

Validation:
- 25 focused test methods passed on abdin_replica(POS) (27 Odoo test-stat entries), including raw driver-row regression coverage; external report queries mocked.
- Targeted ab_sales_promo_report upgrade succeeded.
- AST comparison confirmed unchanged SQL preparation, discount formulas, tolerance, invoice-date predicate and product-scope helper; translated strings unchanged.
- Only the four approved module files differ from HEAD.
