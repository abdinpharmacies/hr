# ab_website_sale_product Session Notes

Date: 2026-05-04

This note summarizes the eCommerce integration work done for Abdin products during this session.

## Goal

Expose products from the custom `ab_product` catalog in Odoo Website/eCommerce without rewriting Odoo's native shop flow.

The chosen approach is to keep `ab_product` as the master catalog and sync selected records into native Odoo `product.template` / `product.product`, because `website_sale`, `/shop`, cart, checkout, payments, and sale orders all expect native product records.

## Addon Created

Created a new addon:

```text
custom-addons/ab_website_sale_product
```

It depends on:

```python
["website_sale", "ab_product"]
```

The existing `ab_website` branding addon was left untouched.

## Main Features Implemented

### Product Sync

Added sync logic on `ab_product` in:

```text
custom-addons/ab_website_sale_product/models/ab_product.py
```

The sync creates or updates one native `product.template` per `ab_product`.

Mapped fields include:

- `ab_product.name` / `product_card_name` -> `product.template.name`
- `ab_product.code` -> `default_code`
- `ab_product.default_price` -> `list_price`
- `ab_product.default_cost` -> `standard_price`
- `ab_product.is_service` -> product type
- `ab_product.allow_sale` -> `sale_ok`
- `ab_product.allow_purchase` -> `purchase_ok`
- `ab_product.active` -> native product active state
- `ab_product.description` -> ecommerce descriptions
- first `barcode_ids.name` -> variant barcode
- `groups_ids` -> website public categories
- `tag_ids` -> native product tags

The first version uses:

```text
1 ab_product = 1 product.template = 1 product.product
```

### Model Links

Added links between native Odoo products and Abdin products in:

```text
custom-addons/ab_website_sale_product/models/product_template.py
```

Added:

- `product.template.ab_product_id`
- `product.product.ab_product_id` as a stored related field

A unique index prevents linking one `ab_product` to multiple ecommerce templates.

### Sale Order Line Link

Added a stored related field in:

```text
custom-addons/ab_website_sale_product/models/sale_order_line.py
```

Added:

- `sale.order.line.ab_product_id`

This lets ecommerce orders keep a direct reference back to the source `ab_product`.

### Backend Buttons

Added buttons on the `ab_product` form:

- `Sync eCommerce Product`
- `Open eCommerce Product`
- `Open Website Page`

Added list/form fields:

- `website_sale_available`
- `website_product_synced`
- `website_product_tmpl_id`
- `website_product_is_published`

### Bulk Sync Action

Added a server action:

```text
Action > Sync to eCommerce
```

This action works from `ab_product` list/form views and calls:

```python
records.action_sync_website_product()
```

### Scheduled Sync

Added an inactive cron:

```text
Website Sale: Sync Abdin Products
```

It calls:

```python
model.cron_sync_website_products()
```

The cron is inactive by default so a full catalog sync does not start automatically.

### Website/eCommerce Menu

Added a quick backend menu under Website:

```text
Website > eCommerce > Products > Abdin Products
```

This opens an `ab_product` action filtered to active sellable website-available products that are not yet synced.

Users can select rows there and run:

```text
Action > Sync to eCommerce
```

### Search Filters

Added filters to the `ab_product` search view:

- `Website Available`
- `Not Synced`
- `Synced`
- `Published`

## Install Issue Fixed

The first install failed because Odoo 19 rejects inherited view XPath selectors using `@string`.

Original problem:

```xml
//group[@string='Product Details']
```

Fixed by anchoring on a stable field instead:

```xml
//field[@name='code']
```

## Database Checks Performed

After the addon was installed, the live database showed:

- module state: `installed`
- eligible active sellable website products: `30419`
- synced ecommerce templates at that moment: `0`

This confirmed that installation does not automatically sync the full catalog.

## Validation Performed

Validation steps run during the session:

```text
python -m compileall
lxml XML parse checks
Odoo addon namespace import
isolated full install in temporary databases
```

The isolated installs completed successfully after the XPath fix and after adding the menu.

Temporary validation databases were dropped after use.

## Operational Notes

Installing the addon only adds the bridge, fields, views, actions, and menu.

To create native ecommerce products:

1. Open `Website > eCommerce > Products > Abdin Products`.
2. Select products.
3. Use `Action > Sync to eCommerce`.
4. The synced products appear in the normal ecommerce products menu and on `/shop` if published.

Because there were more than 30,000 eligible products, sync should be tested on a small batch first before running a full catalog sync.

## Files Added Or Changed

```text
custom-addons/ab_website_sale_product/__init__.py
custom-addons/ab_website_sale_product/__manifest__.py
custom-addons/ab_website_sale_product/hooks.py
custom-addons/ab_website_sale_product/models/__init__.py
custom-addons/ab_website_sale_product/models/ab_product.py
custom-addons/ab_website_sale_product/models/product_template.py
custom-addons/ab_website_sale_product/models/sale_order_line.py
custom-addons/ab_website_sale_product/views/ab_product_views.xml
custom-addons/ab_website_sale_product/views/product_template_views.xml
custom-addons/ab_website_sale_product/views/website_sale_menus.xml
custom-addons/ab_website_sale_product/data/server_actions.xml
custom-addons/ab_website_sale_product/data/ir_cron.xml
custom-addons/ab_website_sale_product/tests/__init__.py
custom-addons/ab_website_sale_product/tests/test_ab_website_sale_product.py
```
