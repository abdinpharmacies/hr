commit 578b0e729f216f30eef56604c41f518c89698fa8
Author: itharrefaat5 <itharrefaat5@gmail.com>
Date:   Mon Aug 17 12:28:58 2026 +0300

    ab_stock_report/ FIX slow sales report using ordy by sec_insert_date desc instead of std_id desc

User-facing changes:

- Improved stock movement report performance for recent sales movement loading.

Files changed:

- `ab_stock_report/models/ab_stock_report_cache.py`

## Current changes before commit

User-facing changes:

- Keep each Stock Movements wizard on its own private JSON cache, including movement group, product serial, date, fetch mode, loaded rows, offset, `has_more`, and empty-result state.
- Keep opening the wizard lazy: BConnect is queried only after pressing Sales, Purchase, or Transfer.
- Without From Date, fetch the latest movements using the Last Movements limit, defaulting to 10.
- With From Date, ignore and hide Last Movements, then load matching movements in 100-row batches.
- Add a Load More action for date-range mode and hide it when all rows are loaded.
- Reuse the current wizard cache on repeated tab clicks and refetch when the date, limit, product, or fetch mode changes.
- Use `sec_update_date` for movement datetime, From Date filtering, SQL ordering, Python sorting, cache payloads, and displayed lines.
- Remove `sec_insert_date` fallback usage from the stock movement providers.
- Include sales returns in the Sales / Return family fetch path.
- Add Arabic translations for the new Load More and cache status labels.

Files changed:

- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/models/ab_stock_report_cache.py`
- `ab_stock_report/views/ab_stock_report_views.xml`
