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

- Add a fourth Store Balances & Sales tab to the product Stock Movements wizard.
- Show active configured `ab_store` rows for the selected product with cached main-server balance, direct-store balance, difference, and 90-day sales buckets.
- Add a persistent product/store cache with a unique product-store key and read-only internal-user access.
- Add single-store direct refresh through `store.ip1`, explicit missing-IP/failure/cancel statuses, direct timestamps, and latest error text.
- Add a persistent bulk direct-refresh job with progress counters, cooperative cancellation, per-store commits, and reuse of the existing stock report worker and cron fallback.
- Add toolbar actions to refresh main-server data, update all stores, cancel an update, and refresh progress.
- Add Arabic translations for the new tab, columns, actions, statuses, and errors in both Arabic language files.
- Add `ab_store` as a manifest dependency.
- Move the Store Balances & Sales row refresh action to the first column and Direct Status to the last column.
- Display balance and sales numbers without trailing zero padding, while showing a single `0` for empty values.
- Hide the three day-bucket columns by default behind the optional columns menu and keep Total 90 Days visible.
- Tighten Store Balances & Sales table column widths to fit the displayed content more closely.
- Add a branch dropdown filter for Store Balances & Sales using the same active-store and EPlus-serial criteria as the report lines.
- Place the branch filter on the left side of the Store Balances & Sales one2many control panel when the list pager renders.
- Display Sales, Purchase, and Transfer movement prices and quantities without unnecessary trailing zeros while keeping raw float fields unchanged.

Files changed:

- `ab_stock_report/__manifest__.py`
- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/models/ab_stock_report_store_balance.py`
- `ab_stock_report/models/__init__.py`
- `ab_stock_report/security/ir.model.access.csv`
- `ab_stock_report/static/src/js/ab_stock_report_dialog.js`
- `ab_stock_report/static/src/scss/ab_stock_report.scss`
- `ab_stock_report/views/ab_stock_report_views.xml`
