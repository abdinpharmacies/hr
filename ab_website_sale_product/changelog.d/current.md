# Website Sale Product change log

## Current changes before commit:

- Refresh E-Plus first and finish imports for uploaded image codes before building the synchronization plan.
- Read the E-Plus selling price through the existing connector using parameterized, batched catalog reads without NOLOCK.
- Link or create website templates, apply valid images and prices, enable eligible products, and publish them in a per-product transaction.
- Record old/new website and source prices, actor and time in the product chatter; retain replica write protection.
- Publish eligible products even when their image already matches; report missing records, invalid prices and denied operations.
- Add English/Arabic publication results and focused import, price, rollback, permissions and retry coverage.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`

Validation:

- Targeted upgrade of both affected modules on `codex_eplus_sync_20261104`, ports `5069/5072`, passed.
- Focused suite: 29 tests, zero failures/errors; `/tmp/image-publication-verified.log`.
- External E-Plus reads were mocked in tests; no live product publication was executed.
- The isolated filestore lacks some pre-existing attachments; Odoo logged missing fixture attachments without test failures.
- Both Arabic catalogs pass `msgfmt --check-format`; Python AST and `git diff --check` pass.
- Runtime `en_US`/`ar_001` checks passed for the new publication counter and E-Plus stock action.

Operational boundary:

- A product replica still requires the authoritative product to arrive through supported replication. Missing products and prohibited master-price/availability writes are reported, not bypassed.

## Recent commits

Commit: `fe401bde`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_website_sale_product/IMP: label code-based product publishing clearly`

User-facing changes:

- Clarify that the code-based product action publishes products, and translate its labels.

Files changed:

- `ab_website_sale_product/README_website_product_sync.md`
- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/views/ab_product_kanban_views.xml`
- `ab_website_sale_product/views/add_many_by_codes_views.xml`

Commit: `124ad69c`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_website_sale_product/FIX: read Eplus catalog without ODBC`

User-facing changes:

- Read E-Plus catalog names through the native SQL Server connector so queued imports run without ODBC on the website server.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`

Commit: `6963a11a`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/FIX: recover catalog imports on product replicas`

User-facing changes:

- Complete website draft sync for products already present on the replica while preserving product-master write protection.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`

Commit: `b3af5683`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/FIX: create unpublished products for matched Eplus items`

User-facing changes:

- Create unpublished website products for Eplus-linked catalog items without website products.
- Show the queued item count and preserve existing publication status.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`

Commit: `a701a554`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/FIX: show safe error when Eplus stock refresh fails`

User-facing changes:

- Show a translated connection error and preserve the previous Eplus snapshot when refresh fails.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`

Commit: `796d2bcd`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/FIX: retry Eplus catalog imports after connection timeouts`

User-facing changes:

- Retry catalog import jobs when the Eplus connection times out, up to the configured limit.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`

Commit: `fc7b8062`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/IMP: create unpublished website products from Eplus drafts`

User-facing changes:

- Create linked, unpublished website products from Eplus catalog drafts.
- Complete website products for previously imported drafts and protect Eplus refresh access.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/product_template.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`

Commit: `f862b1c7`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/IMP: sync images for unlinked catalog products`

User-facing changes:

- Include active catalog products without website templates in image synchronization.
- Create an unpublished website product when a valid matching image is synchronized.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`

Commit: `e95e0803`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/IMP: import unmatched Eplus items as catalog drafts`

User-facing changes:

- Add Eplus draft status and queue-based catalog import from stock snapshots.
- Link existing Abdin products before attempting draft creation.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/tests/__init__.py`
- `ab_website_sale_product/tests/test_eplus_catalog_import.py`
- `ab_website_sale_product/views/ab_product_kanban_views.xml`
- `ab_website_sale_product/views/ab_product_views.xml`

## Earlier catalog commit

Commit: `f4a3129c`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product/IMP: show archived products and website status in catalog`

User-facing changes:

- Show active and archived Abdin products together in the Website catalog list.
- Add a website status column and archived filter.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/tests/test_website_product_sync.py`
- `ab_website_sale_product/views/ab_product_kanban_views.xml`
- `ab_website_sale_product/views/ab_product_views.xml`
- `ab_website_sale_product/views/website_sale_menus.xml`

## Earlier commits

Commit: `d0265c08`
Author: Mohamed Fawzy
Date: 2026-11-10
Original subject: `ab_website_sale_product/FIX: combine unprocessed customer uploads`

User-facing changes:

- Combine review rows from unprocessed customer uploads in one review batch.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/docs/legacy-customers.md`
- `ab_website_sale_product/models/legacy_activation_batch.py`
- `ab_website_sale_product/tests/test_legacy_staging_rows.py`

Commit: `b20d02cf`
Author: Mohamed Fawzy
Date: 2026-11-10
Original subject: `ab_website_sale_product/FIX: open stored customer rows without codes`

User-facing changes:

- Open the latest stored review directly from Eplus Stock even before creating activation codes.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/docs/legacy-customers.md`
- `ab_website_sale_product/models/legacy_activation_batch.py`
- `ab_website_sale_product/tests/test_legacy_staging_rows.py`

## Earlier review commit

Commit: `9eb88472`
Author: Mohamed Fawzy
Date: 2026-11-10
Original subject: `ab_website_sale_product/IMP: unify legacy customer review rows`

User-facing changes:

- Store every customer row for review and show rows from repeated uploads in one table.
- Hide only fully identical rows automatically and display the hidden duplicate count.
- Open the latest completed batch directly from Eplus Stock.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/docs/legacy-customers.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/legacy_activation_batch.py`
- `ab_website_sale_product/models/legacy_staging_row.py`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/security/legacy_customer_rules.xml`
- `ab_website_sale_product/services/legacy_csv.py`
- `ab_website_sale_product/tests/__init__.py`
- `ab_website_sale_product/tests/test_legacy_staging_rows.py`
- `ab_website_sale_product/views/legacy_customer_button.xml`
- `ab_website_sale_product/views/legacy_customer_views.xml`

## Earlier customer import commit

Commit: `47990e20`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_website_sale_product/IMP: add reviewed legacy customer imports and activation codes`

User-facing changes:

- Add customer CSV review and selective activation-code generation.
- Add protected customer review and code exports.

Files changed:

- `ab_website_sale_product/__init__.py`
- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/changelog.d/2026-11-04-csv-column-review.md`
- `ab_website_sale_product/changelog.d/2026-11-04-legacy-customer-codes.md`
- `ab_website_sale_product/controllers/__init__.py`
- `ab_website_sale_product/controllers/legacy_export.py`
- `ab_website_sale_product/docs/legacy-customers.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/legacy_activation_batch.py`
- `ab_website_sale_product/models/legacy_customer.py`
- `ab_website_sale_product/models/legacy_import_issue.py`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/security/legacy_customer_rules.xml`
- `ab_website_sale_product/services/legacy_activation.py`
- `ab_website_sale_product/services/legacy_csv.py`
- `ab_website_sale_product/static/src/js/legacy_process_batch.js`
- `ab_website_sale_product/views/legacy_customer_button.xml`
- `ab_website_sale_product/views/legacy_customer_views.xml`

## Earlier commit

Commit: `93642f54`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_website_sale_product/FIX: preserve category description languages`

User-facing changes:

- Preserve English and Arabic website category descriptions during classification sync.

Files changed:

- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/product_classification.py`
- `ab_website_sale_product/tests/test_product_classification.py`
