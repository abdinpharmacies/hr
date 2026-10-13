# Event-driven classification dashboard updates

## Recent relevant commit

Commit: `bd92de2a90422a41e543fab782b550ac80df0dab`
Author: Mohamed Fawzy
Date: 2026-10-05
Original commit subject: `ab_website_sale_product/feat: add queued product categorization and review workflow`

- Add the product classification dashboard, queued processing, progress tracking and review workflow.

Files changed:

- `models/product_classification.py`
- `static/src/js/product_classification.js`
- `__manifest__.py`

## Current changes before commit:

- Stop requesting the classification dashboard every three seconds.
- Notify open classification dashboards after a product is added or its catalog eligibility changes.
- Refresh classification run progress after committed server-side changes through the Odoo bus.
- Keep background refresh requests silent so they do not display Odoo's global loading label.
- Debounce notifications from batch changes into one dashboard request.
- Open the exact uncategorized product records by selecting the dashboard metric, with editable website categories in website scope.
- Count Odoo's Gift Card and Top-up eWallet products separately and exclude them from missing-category coverage and classification runs.

Files changed:

- `__manifest__.py`
- `models/product_classification.py`
- `static/src/js/product_classification.js`
- `static/src/xml/product_classification.xml`
- `views/product_classification_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/check_classification_polling.cjs`
- `docs/classification.md`
- `changelog.d/2026-10-05-event-driven-classification-dashboard.md`

Validation:

- Python model and manifest syntax checks passed.
- Classification template and backend view XML syntax checks passed.
- Confirmed that the uncategorized action serializes the exact inverse category domain.
- Exported the Odoo 19 POT and validated both Arabic catalogs with `msgfmt --check-format`.
- Read-only live verification returned 31,263 classified products, two system gift products, zero uncategorized products, zero pending products and 100% coverage.
- Confirmed that the gift action returns only Gift Card and Top-up eWallet and that the uncategorized action returns no records.
- Targeted `ab_website_sale_product` upgrade completed on `ecom19`; the module remained installed and the Arabic gift action resolved to `منتجات الهدايا`.
- The two overlapping event-refresh race checks passed.
- Confirmed that the dashboard contains no recurring timer and uses a silent ORM request after bus notifications.
- `git diff --check` passed.
