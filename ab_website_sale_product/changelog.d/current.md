# Website Sale Product change log

## Current changes before commit:

- Keep the success notification and reopen the synchronization report without a client-side exception by including explicit form views in the chained window action.
- Cover real completion actions for success, warning and empty results, without mocking report-action generation.

Files changed:

- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`
- `ab_website_sale_product/changelog.d/current.md`

Validation:

- Six completion tests passed on `codex_eplus_sync_20261104`, zero failures/errors; `/tmp/image-sync-views-fix-tests.log`.
- Executed the extracted `_preprocessAction` function from deployed asset `b5f69a7/web.assets_web.min.js`: the prior action reproduces the reported missing-map TypeError; explicit form views pass.
- Captured asset SHA-256: `e14aa8ca3388910911e2c237012ebf5b4a59351a411992976e22bca5c0e81706`.
- This is function-level JavaScript validation, not an interactive browser run. No product synchronization was executed for this fix.
- No user-facing source strings changed; existing English and both Arabic translations are retained.
- Production needs a Python service restart only; no database upgrade is required for this correction.

## Recent commits

Commit: `464d582d`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_website_sale_product/IMP: publish image matches from replicated products with Eplus fallback`

User-facing changes:

- Match uploaded images against active and archived Abdin products.
- Use replicated ab_product as the primary catalog and price source, including archived records. Look up E-Plus only for image codes absent from that catalog; missing master prices never trigger fallback.
- Reuse a unique existing website template by its source link or exact code, including archived templates. Reject conflicting links, duplicate codes, unsupported variant adoption and templates outside the selected companies.
- Unarchive, enable sales and publish the website template after a valid image and source price, without changing the replicated product's price, archive state or sale flags.
- For missing codes, read E-Plus names and prices through the existing connector and create/reuse only the native website product. Preserve the external item identity and link the same template when its replicated source becomes available during synchronization.
- Reject duplicate codes, conflicting external identities and ambiguous image matches. E-Plus outages are reported for fallback items while existing source products can still publish. Audit changed website prices with actor and timestamp.
- Retain explicit image-based website activation during later source synchronization while preserving manual website unpublishing.
- Show persistent completion feedback with actual counts, distinguish review items/no matches, and keep the report open.
- Translate new model labels and messages in both Arabic catalogs and preserve existing translations.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/product_template.py`
- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`

Validation:

- Targeted upgrade on `codex_eplus_sync_20261104`, alternate ports `5069/5072`, passed.
- Initial primary-source/fallback, completion and catalog suite: 38 tests, zero failures/errors; `/tmp/image-fallback-tests.log`.
- Expanded final suite: 73 of 74 tests passed, with one failure and zero errors; `/tmp/image-fallback-final-validation.log`. All 23 publication/fallback tests, completion, upload, catalog, image matching and four targeted existing-sync tests passed.
- The remaining failure is `TestWebsiteCategoryMapping.test_l3_group_maps_to_canonical_category`: the validation database returns no category for Body Care L3. The category classification implementations are unchanged by this work.
- Updated image test setup to explicitly create native templates and use database-backed test attachments; preserved English expectations for category assertions.
- Earlier completion/upload suite: 10 tests passed; `/tmp/image-completion-tests.log`.
- Both Arabic catalogs pass `msgfmt --check-format`; Python syntax and `git diff --check` pass.
- Runtime `en_US`/`ar_001` verification passed for both new template labels, nine source/completion messages, the E-Plus stock action and the Arabic success notification. All 16 changed UI source strings have both Arabic translations, and the unique-index message is translated too.
- Uses native Odoo 19 notifications; no shared frontend overrides or new external writes.
- Isolated filestore lacks some existing attachments; missing-file notices remain in the validation logs.
- External E-Plus reads were mocked. No live-server upgrade, product publication, or change to main-server replication permissions was performed.

Operational boundary:

- Replicated ab_product records remain controlled by the main server. The fallback creates no local ab_product record and does not bypass replication permissions. Missing/invalid master prices and conflicting links are reported without publication.
- Fallback products use native stock behavior until linked to the replicated source; this workflow does not import or fabricate inventory quantities.
- No live E-Plus connection or production deployment was used for this validation. Deployment requires a targeted module upgrade for the new template fields.



Commit: `d3340f5e`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_website_sale_product/IMP: price and publish products during image sync`

User-facing changes:

- Refresh E-Plus, link image products, validate selling prices, and publish eligible products after image synchronization.
- Audit price changes and report missing or protected product records.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`

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
