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

## Current changes before commit

User-facing changes:

- Restore the premium SaaS-style Stock Movements wizard assets and manifest registration after the UI files were accidentally broken.
- Keep the wider dialog shell, scoped neutral palette, modern product header, filter bar, segmented movement tabs, status chips, empty states, and data-grid table styling.
- Keep Last Movements visible beside From Date, read-only and muted when From Date is selected.
- Keep the compact clear button for From Date and the normal cursor on the date input.
- Mirror Load More into the modal footer strip opposite Save/Discard while preserving the original Odoo object action.
- Render cache/status chips through translated selection display fields so restored or stale wizard values do not appear in English for Arabic users.
- Convert the header, product serial, movement count, and updated labels to validator-safe Odoo labels so their Arabic view translations load correctly.
- Render the loaded-row count as a numeric field plus translated view label, avoiding the English computed text `movements loaded`.
- Add the missing wizard view translation reference for `From Date`.
- Convert the Load More footer `More movements available` message to a translated Odoo view label and add spacing between the loaded count and its Arabic label.
- Hide the Last Movements filter block while From Date mode is active.
- Add Arabic translations for the new display-only status fields and selection labels in both `ar.po` and `ar_001.po`.
- Preserve the existing stock movement workflow, BConnect providers, cache payload behavior, fetch modes, `sec_update_date` logic, and Load More pagination logic.

Files changed:

- `ab_stock_report/__manifest__.py`
- `ab_stock_report/changelog.d/2026-08-13-stock-movement-report.md`
- `ab_stock_report/i18n/ar.po`
- `ab_stock_report/i18n/ar_001.po`
- `ab_stock_report/models/ab_stock_report.py`
- `ab_stock_report/static/src/js/ab_stock_report_dialog.js`
- `ab_stock_report/static/src/scss/ab_stock_report.scss`
- `ab_stock_report/views/ab_stock_report_views.xml`
