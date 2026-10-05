# Taxonomy descriptions and Shop by Need

## Recent relevant commit

Commit: `083e324f3b56f0cf60f0064b3645d25e3743b3f0`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/docs: record website sync commits`

- Record the module’s recent implementation history.

Files changed:

- `changelog.d/2026-09-29-website-sync-local-commits.md`

## Current changes before commit:

- Fix taxonomy preparation to reuse correctly placed aliases and retain similarly named categories in other branches.
- Add editable English/Arabic descriptions and a main-category descriptions shortcut.
- Add ten approved shop needs and an editable needs column for main categories and subcategories.
- Display category-derived needs on products, with main-category inheritance and child-only mappings.
- Apply the targeted live repair: all 77 bindings ready, all 431 existing category records and parents retained, 25 missing categories created.
- Validate clean installation with 78 passing tests, focused permissions/filtering checks, both Arabic catalogs and live runtime translations.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/product_classification.py`
- `models/shop_need.py`
- `data/classification_taxonomy.xml`
- `data/shop_needs.xml`
- `views/product_classification_views.xml`
- `views/ab_product_views.xml`
- `views/product_template_views.xml`
- `static/src/js/product_classification.js`
- `static/src/xml/product_classification.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `docs/classification.md`
- `changelog.d/2026-10-04-taxonomy-shop-needs.md`
