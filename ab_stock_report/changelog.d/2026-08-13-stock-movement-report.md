commit 82e1d02727dbe1146527afbede2b08695ca2cc36
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Tue Aug 18 15:32:38 2026 +0300

    ab_stock_report(#2019)/feat: add local storage to wizard and load more for more than 100+

User-facing changes:

- Keep each Stock Movements wizard on its own private JSON cache for loaded movement rows.
- Add date-range loading for more than 100 movements while preserving lazy Sales, Purchase, and Transfer fetches.
- Keep Load More available only when the current cached date-range result has more rows.
- Preserve `sec_update_date` as the displayed and sorted movement date.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/views/ab_stock_report_views.xml`

commit cd9a5a1b7eda2039ce3bf22f5c09f076f6358440
Author: emadco88 <emadco88@gmail.com>
Date:   Wed Aug 19 16:19:20 2026 +0300

    ab_stock_report/ FIX slow Sales report by adding indexes

User-facing changes:

- Keep the Sales movement report responsive by narrowing the BConnect sales query path.
- Add focused test coverage for the sales query join and filters.

Files changed:

- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/tests/__init__.py`
- `ab_stock_report/tests/test_stock_report_sales_query.py`

commit f53c4681caefdafb22c4251bcd7166817ee521fb
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Wed Aug 19 15:33:22 2026 +0300

    ab_stock_report(#2019)/fix: translate the task words

User-facing changes:

- Improve Arabic translations and display wording for the Stock Movements wizard.
- Preserve translated task/status labels in the refreshed wizard UI.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/static/src/scss/ab_stock_report.scss`
- `ab_stock_report/views/ab_stock_report_views.xml`

## Current changes before commit

User-facing changes:

- Calculate transfer-in and transfer-out quantities with the authoritative Item Catalog unit conversion factors.
- Avoid incorrect zero quantities when transfer-side unit conversion fields are empty.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/models/ab_stock_report_cache.py`
