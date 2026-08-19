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

- Redesign the Stock Movements wizard as a wider premium SaaS-style dialog with a scoped neutral palette, subtle borders, compact spacing, and modern typography.
- Add module-scoped backend assets for the stock report dialog presentation, including a tiny JS dialog-class tagger used only to style this wizard's modal shell and footer.
- Rework the wizard header, product identity area, filter bar, Sales/Purchase/Transfer segmented control, status bar, empty states, movement table, pager prominence, Load More action, and Save/Discard footer styling.
- Keep the Last Movements filter visible beside From Date and mirror the Load More action into the modal footer strip opposite Save/Discard.
- Make Last Movements read-only and visually muted when From Date is selected, clarifying that date-range loading uses the fixed batch flow.
- Add a compact clear button for From Date and keep the date input cursor neutral on hover.
- Add Arabic translations for the new and updated UI text in both supported Arabic translation files.
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
