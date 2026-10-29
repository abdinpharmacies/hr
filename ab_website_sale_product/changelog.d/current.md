# Website Sale Product change log

## Recent commits

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

## Current changes before commit:

- Restore the E-Plus stock refresh on the store server by using the available SQL Server connection backend.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/eplus_stock_snapshot.py`
