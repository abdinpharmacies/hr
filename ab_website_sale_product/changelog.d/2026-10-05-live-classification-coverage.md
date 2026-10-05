# Live classification coverage and new-product runs

## Recent relevant commit

Commit: `083e324f3b56f0cf60f0064b3645d25e3743b3f0`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/docs: record website sync commits`

- Record the existing synchronization implementation history.

Files changed:

- `changelog.d/2026-09-29-website-sync-local-commits.md`

## Current changes before commit:

- Keep current catalog category coverage visible independently of the last run's processing percentage; refresh counts automatically as products arrive.
- Count actual website category assignments, including legacy categories; use saved assignments for Abdin products without linked website templates.
- Start only never-attempted products without categories, plus explicitly reset decisions. Keep previous review and failed products in their original run and preserve manual, ignored and forced decisions.
- Reject empty starts and recheck eligibility during background snapshot preparation.
- Select the latest run for the chosen scope/website and improve metric-label contrast.
- Add exported Arabic translations in both language catalogs and document the distinction between current coverage and historical run progress.

Files changed:

- `models/product_classification.py`
- `static/src/js/product_classification.js`
- `static/src/xml/product_classification.xml`
- `static/src/scss/product_classification.scss`
- `tests/test_product_classification.py`
- `tests/test_classification_ui.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `docs/classification.md`
- `changelog.d/2026-10-05-live-classification-coverage.md`

Validation:

- 77 non-browser regression tests passed. Browser test passed separately after isolating the test database and rebuilding stale generated test assets.
- Browser check verified that adding an uncategorized product decreases coverage automatically while completed-run processing remains 100%, and that Start/Pause/Resume/Stop still work.
- Rollback-only transactional checks covered new-only membership, existing review/failed/ignored decisions, empty starts, new-arrival percentages, scope isolation, explicit reset, all-Abdin inactive/unlinked records, cross-scope history, and denied public access (`/tmp/ab_coverage_checks.py`).
- Two polling race checks, Python/XML syntax, both Arabic catalogs' format checks, and whitespace checks passed.
- Targeted local module upgrade succeeded; the eCommerce master was gracefully reloaded to activate the Python code. No classification run was started and no product categories were assigned by this task.
- Read-only live verification: 31,255 website products, 31,253 with categories, two without categories, zero new products eligible for Start. The displayed coverage is 99.99%; older unresolved attempts remain available through Run History.
- The reloaded live server returned the five new dashboard labels in Arabic through its web translation endpoint; the action name also differed between en_US and ar_001.
