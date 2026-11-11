# Website product replica integration change log

## Current changes before commit:

- Install the optional integration automatically when website product sync and Odoo replication are both installed.
- Allow Settings administrators to update only `ab_product.website_sync_pending` through a module-owned security rule.
- Preserve replica restrictions on product creation, product codes, external identifiers, prices, and all other fields.
- Test unpublished draft creation with replica protection enabled, repeated import, mixed matched/unmatched batches, and denied normal-user access.

Files changed:

- `ab_website_sale_product_replication/__init__.py`
- `ab_website_sale_product_replication/__manifest__.py`
- `ab_website_sale_product_replication/security/website_sync_rule.xml`
- `ab_website_sale_product_replication/tests/__init__.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Validation:

- Clean install on `ecom19_storefront_validation_20261109`, ports `5069/5072`: four integration tests passed, zero failures/errors, with real replica restrictions and install mode disabled.
- POT export `/tmp/ab_website_sale_product_replication.pot` contains no translatable terms. This integration adds no menus, views, groups, or user-facing messages.
- Manifest retains Abdin Pharmacies ownership and developer Mohamed Fawzy. No hooks, demo data, migrations, or new business models.
- Log: `/tmp/eplus_replica_recovery_validation.log`. No prior commits exist for this new module.
