commit ffce00968ebe5faad6741abf8b73c5413784989c
Author: emadco88 <emadco88@gmail.com>
Date:   Mon Aug 24 16:59:44 2026 +0300

    ab_stock_report/ UPD simplify view

User-facing changes:

- Simplified the Stock Movements wizard layout while preserving the tabbed report workflow.

Files changed:

- `ab_stock_report/views/ab_stock_report_views.xml`

commit 4f20b3c1924d39ba5d45f78e1e14ac12680515e8
Author: emadco88 <emadco88@gmail.com>
Date:   Mon Aug 24 16:50:35 2026 +0300

    ab_stock_report/ FIX conversion factor

User-facing changes:

- Calculate transfer quantities with the authoritative Item Catalog conversion factors.
- Avoid incorrect zero quantities when transfer-side unit conversion fields are empty.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/models/ab_stock_report_cache.py`

commit d8706f167625921044d592f5f3c5c6bb748a04a4
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Sun Aug 23 13:48:06 2026 +0300

    ab_stock_report/FIX(#2184): Remove Trailing Zeros from Movement Numbers

User-facing changes:

- Display movement, balance, and sales quantities without unnecessary trailing zeros.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/views/ab_stock_report_views.xml`

commit cd21a5797610860bfc34da2eae4e15aa95293990
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Thu Aug 20 15:42:35 2026 +0300

    ab_stock_report/FEAT(#2108):Add a fourth Store Balances & Sales tab to the product-specific ab_stock_report wizard

User-facing changes:

- Added the Store Balances & Sales tab to the product stock report wizard.
- Added main-server balance/sales cache rows and direct branch balance refresh tracking.

Files changed:

- `ab_stock_report/__manifest__.py`
- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/__init__.py`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/models/ab_stock_report_store_balance.py`
- `ab_stock_report/security/ir.model.access.csv`
- `ab_stock_report/static/src/js/ab_stock_report_dialog.js`
- `ab_stock_report/static/src/scss/ab_stock_report.scss`
- `ab_stock_report/views/ab_stock_report_views.xml`

## Current changes before commit

User-facing changes:

- Filter Store Balances & Sales immediately when a branch is selected in the tab.
- Limit Store Balances & Sales branch choices and rows to stores with working balance enabled.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_store_balance.py`
- `ab_stock_report/tests/test_stock_report_sales_query.py`
- `ab_stock_report/views/ab_stock_report_views.xml`
