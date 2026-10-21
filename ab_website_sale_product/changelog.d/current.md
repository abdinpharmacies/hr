# Website Sale Product change log

## Recent commits

Commit: `a624d4de`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_website_sale_product/I18N: complete Arabic product administration translations`

User-facing changes:

- Complete Arabic translations for product administration screens.

Files changed:

- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`

Commit: `5becb8a5`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_website_sale_product/IMP: open uncategorized products for category editing`

User-facing changes:

- Open uncategorized products for category editing from the classification screen.

Files changed:

- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/product_classification.py`
- `ab_website_sale_product/static/src/js/product_classification.js`
- `ab_website_sale_product/static/src/xml/product_classification.xml`
- `ab_website_sale_product/views/product_classification_views.xml`

## Current changes before commit:

- Keep website category descriptions in English for English visitors and Arabic for Arabic visitors when syncing the approved taxonomy.
- Add a regression test for the two language values and translate the new validation message in both Arabic catalogs.

Files changed:

- `ab_website_sale_product/changelog.d/current.md`
- `ab_website_sale_product/models/product_classification.py`
- `ab_website_sale_product/tests/test_product_classification.py`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
