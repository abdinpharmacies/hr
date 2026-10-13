# Synchronization progress layout

## Recent relevant commit

Commit: `bd92de2a90422a41e543fab782b550ac80df0dab`
Author: Mohamed Fawzy
Date: 2026-10-05
Original commit subject: `ab_website_sale_product/feat: add queued product categorization and review workflow`

- Introduce the classification dashboard used as the visual reference for synchronization progress.

Files changed (relevant to this layout):

- `static/src/xml/product_classification.xml`
- `static/src/scss/product_classification.scss`

## Current changes before commit:

- Match Eplus Inventory Sync and Website Product Sync to the classification dashboard with rounded cards, large counters, status badges, and slim progress bars with adjacent percentages.
- Preserve existing fields, action buttons, visibility conditions, sync calculations, and refresh behavior through inherited form views and module-scoped styles.
- Keep the existing classification layout and shared frontend components unchanged by this UI work.
- Add the exported view terms to both Arabic catalogs without replacing existing translations.
- Separate concurrent classification notification changes into their own changelog entry.

Files changed:

- `__manifest__.py` (register the inherited views and scoped stylesheet)
- `views/sync_progress_views.xml`
- `static/src/scss/sync_progress.scss`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-05-sync-progress-layout.md`

Validation:

- Targeted upgrade of `ab_website_sale_product` passed on the idle test database `ab_classification_test_20260930`, using a separate data directory with cron and queue runners disabled.
- Both combined form views retain every original field and button attribute; English and Arabic runtime views differ as expected.
- XML parsing, SCSS compilation, manifest load order, all 13 exported UI terms in both catalogs, `msgfmt --check-format`, and whitespace checks passed.
- Eight browser layout checks passed: both synchronization forms in `en_US` and `ar_001` at 1440px and 390px, checking card radius, progress height, counter size, RTL direction, percentages, and page overflow. The temporary server used ports 5069/5072 and was stopped after validation.
- Regenerated missing cached assets only in the isolated test database; the active `ecom19` database was not upgraded as part of this UI change.
- Final badge-color adjustment passed SCSS compilation. A later screenshot refresh could not authenticate after the temporary browser session expired; the eight layout checks above passed before that cosmetic adjustment.
- No synchronization operation was started; no inventory or product records were modified by UI validation.
