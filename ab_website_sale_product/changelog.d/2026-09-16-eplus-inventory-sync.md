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

Files changed:
- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/data/ir_cron.xml`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/eplus_inventory_sync_job.py`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/product_template.py`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/views/ab_product_professional_views.xml`
- `ab_website_sale_product/views/eplus_inventory_sync_job_views.xml`
- `ab_website_sale_product/views/eplus_stock_snapshot_store_views.xml`
- `ab_website_sale_product/views/eplus_stock_snapshot_views.xml`
- `ab_website_sale_product/views/product_template_views.xml`
- `ab_website_sale_product/views/website_sale_menus.xml`
