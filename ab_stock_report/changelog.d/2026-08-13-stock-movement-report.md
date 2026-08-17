## Current changes before commit

User-facing changes:

- Added the new `ab_stock_report` module to show the latest stock movements for one product from BConnect.
- Added a product-row button in the `ab_product` list view to open the movement report for that product.
- Added a wizard that lets internal users change the movement limit before reloading the report.
- Split the report into three notebook pages for sales/return, purchase/return, and transfer in/out movements.
- Added the movement report columns in English with Arabic translations for the wizard, labels, movement groups, movement types, and action button.
- Added support for sales and sales returns from `r_sales_trans_h` and `r_sales_trans_d` with separate movement rows for insert and return timestamps.
- Added purchase and purchase return movement handling from `pur_trans_h` and `pur_trans_d`.
- Added transfer handling from `Store_Trans_h` and `Store_Trans`, split into source and destination rows.
- Limited each notebook page to the last X rows for its own movement group using SQL ranking instead of client-side slicing.
- Added a local PostgreSQL cache for stock movement rows and switched the wizard to read cache data immediately.
- Added a background refresh job plus cron fallback so BConnect fetches happen asynchronously after the request commits.
- Added a manual `Fetch Now` path for the first direct BConnect pull when no local cache exists yet.
- Added separate `Fetch Sales`, `Fetch Purchase`, and `Fetch Transfers` buttons in the wizard so each movement family can be tested independently.
- Changed the direct-fetch path so the family buttons refresh only their own cache group instead of reloading all movement families.
- Kept the existing cache refresh path available for full report updates.

Files changed:

- `ab_stock_report/__init__.py`
- `ab_stock_report/__manifest__.py`
- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`

## Current changes before commit

User-facing changes:

- Added a From Date filter to the stock movement wizard.
- Applied the selected date to Sales, Purchase, and Transfer queries.
- Included the From Date in the per-wizard JSON cache key so date changes refetch data.

Files changed:

- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/views/ab_stock_report_views.xml`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`

## Current changes before commit

User-facing changes:

- Each new stock movement wizard now starts with an empty private JSON cache.
- Sales, Purchase, and Transfer data is fetched once per wizard tab and reused on subsequent clicks.
- Changing the movement limit causes the selected tab to fetch a new snapshot for that wizard.
- Shared product-level cache records are no longer read by the wizard workflow.

Files changed:

- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`

## Current changes before commit

User-facing changes:

- Changed the report to show three lazy-loading Sales, Purchase, and Transfer buttons as the movement tabs.
- Opening the report no longer fetches or loads all movement families automatically.
- Each tab loads only its own cached data and fetches from BConnect only when that JSON snapshot is missing or stale.
- Replaced per-movement cache rows with one JSON cache snapshot per product, limit, and movement group.
- Added Arabic translations for the new tab labels and lazy-loading guidance.

Files changed:

- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/views/ab_stock_report_views.xml`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/__init__.py`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/security/ir.model.access.csv`
- `ab_stock_report/views/ab_stock_report_views.xml`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
