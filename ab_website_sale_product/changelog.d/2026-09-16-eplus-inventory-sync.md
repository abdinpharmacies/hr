# ab_website_sale_product changelog

## Recent commits

### 4011ff6 - Mohamed Fawzy - 2026-09-01

Original commit subject: `ab_website_sale_product/feat: map website categories`

User-facing changes:
- Added website category mapping support for ecommerce products.
- Added placeholder image support and focused tests for category mapping.

Files changed:
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/static/src/img/placeholders/product_placeholder.jpeg`
- `ab_website_sale_product/tests/__init__.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`

### ddd2b05 - itharrefaat5 - 2026-06-22

Original commit subject: `ab_website_sale_product/ UPD instead of skipping products`

User-facing changes:
- Updated website product sync behavior so existing products are updated instead of skipped.

Files changed:
- `ab_website_sale_product/models/ab_product.py`

### a1b8ee5 - itharrefaat5 - 2026-06-22

Original commit subject: `ab_website_sale_product/ FIX duplicated barcode in Odoo products`

User-facing changes:
- Fixed duplicate barcode handling during ecommerce product synchronization.

Files changed:
- `ab_website_sale_product/models/ab_product.py`

## Current changes before commit

User-facing changes:
- Added full E-Plus to Odoo Inventory sync controls with background job tracking.
- Fixed full-sync progress so skipped/unmapped products no longer make a new sync appear to start around 75%.
- Changed full-sync progress to reflect current Odoo-vs-Eplus inventory match percentage, so already matching products count as complete and only changed quantities remain pending.
- Added E-Plus branch stock snapshots so each product can show branch/store quantities separately while ecommerce inventory still syncs the all-branch total into one Odoo warehouse.
- Added branch stock drilldown buttons, list/pivot views, menu access, and Arabic translations.
- Kept the main E-Plus stock refresh lightweight and moved branch-level stock loading to a separate explicit refresh action.
- Add a direct Refresh Branch Stock button to the E-Plus Branch Stock list and form, so the branch snapshot can be populated from the branch-stock screen itself instead of requiring users to refresh it from the aggregate E-Plus Stock screen.
- Restored the existing Sync Images views to the module manifest so catalog users can open the product image synchronization button again.
- Reworked product image synchronization to scan the configured image root recursively once per run, support flat and nested image layouts, preview results before writing, and update only deterministic non-ambiguous matches.
- Added checksum-based unchanged detection, corrupt-image reporting, missing-image preservation, and a detailed image synchronization report in the existing Sync Images wizard.
- Restricted filesystem image preview/synchronization actions to administrators.
- Display each linked eCommerce product image in the Abdin product kanban, while retaining the cube placeholder for products that are not yet linked.
- Ask for confirmation with an exact match count before replacing genuine existing product images, treat placeholders as products without images, and allow new images to synchronize without overwriting existing ones.

Files changed:
- `ab_website_sale_product/README_product_image_sync.md`
- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/data/ir_cron.xml`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/eplus_inventory_sync_job.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/add_many_by_codes_wizard.py`
- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/models/product_template.py`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/sync_images_views.xml`
- `ab_website_sale_product/tests/test_website_category_mapping.py`
- `ab_website_sale_product/views/ab_product_professional_views.xml`
- `ab_website_sale_product/views/ab_product_kanban_views.xml`
- `ab_website_sale_product/views/eplus_inventory_sync_job_views.xml`
- `ab_website_sale_product/views/eplus_stock_snapshot_store_views.xml`
- `ab_website_sale_product/views/eplus_stock_snapshot_views.xml`
- `ab_website_sale_product/views/product_template_views.xml`
- `ab_website_sale_product/views/website_sale_menus.xml`

Validation:
- Targeted `ab_website_sale_product` upgrade completed successfully on `ecom19`.
- Transactional image-sync QA passed for new-image counting, replacement counting, keeping existing images, stale-confirmation detection, and confirmed replacement; all QA records were rolled back.
- Existing `TestWebsiteCategoryMapping` checks passed with 0 failures and 0 errors across 13 tests.
- Python compilation, XML parsing, `git diff --check`, both Arabic PO format checks, POT export, and runtime `ar_001` translation lookup passed.
- E-Plus branch-stock diagnosis confirmed the source SQL Server has Item_Class_Store data and Odoo aggregate stock has 69,971 active rows, while the Odoo branch snapshot table had 0 rows and no last sync before adding the direct refresh action.
- Targeted `ab_website_sale_product` upgrade is currently blocked by unrelated installed module `abdin_telegram` missing Python package `telebot`; Python compilation, XML parsing, and whitespace checks passed for the branch-stock refresh button change.
