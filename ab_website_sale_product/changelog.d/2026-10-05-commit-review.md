# Commit review — 2026-10-05

Commit: `ea3d8fe21cda30fb5b2e98cb617ff30439f6a704`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `feat(classification): add queued product categorization and review workflow`

User-facing changes:

- Classify products with approved taxonomy, queued processing, review and undo, and live coverage counts.
- Preserve manual decisions and derive shopping needs from taxonomy mappings.

Files changed:

- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/changelog.d/2026-10-01-product-classification.md`
- `ab_website_sale_product/changelog.d/2026-10-04-classification-runner.md`
- `ab_website_sale_product/changelog.d/2026-10-04-force-categorization.md`
- `ab_website_sale_product/changelog.d/2026-10-04-taxonomy-shop-needs.md`
- `ab_website_sale_product/changelog.d/2026-10-05-live-classification-coverage.md`
- `ab_website_sale_product/data/classification_queue.xml`
- `ab_website_sale_product/data/classification_taxonomy.xml`
- `ab_website_sale_product/data/shop_needs.xml`
- `ab_website_sale_product/docs/classification.md`
- `ab_website_sale_product/docs/classification_plan.md`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/README.md`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/ecommerce_categories.csv`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/ecommerce_product_category_rel.csv`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/ecommerce_products.csv`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/manifest.json`
- `ab_website_sale_product/docs/reference/website_ecommerce/categories/notes.md`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/classification_force.py`
- `ab_website_sale_product/models/product_classification.py`
- `ab_website_sale_product/models/shop_need.py`
- `ab_website_sale_product/security/classification_rules.xml`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/services/__init__.py`
- `ab_website_sale_product/services/classification.py`
- `ab_website_sale_product/services/historical.py`
- `ab_website_sale_product/services/web_research.py`
- `ab_website_sale_product/static/src/js/product_classification.js`
- `ab_website_sale_product/static/src/scss/product_classification.scss`
- `ab_website_sale_product/static/src/xml/product_classification.xml`
- `ab_website_sale_product/tests/__init__.py`
- `ab_website_sale_product/tests/check_classification_polling.cjs`
- `ab_website_sale_product/tests/test_classification_ui.py`
- `ab_website_sale_product/tests/test_product_classification.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`
- `ab_website_sale_product/tests/test_website_product_sync.py`
- `ab_website_sale_product/views/ab_product_views.xml`
- `ab_website_sale_product/views/classification_force_views.xml`
- `ab_website_sale_product/views/product_classification_views.xml`
- `ab_website_sale_product/views/product_template_views.xml`

## Validation during commit review

- Python, XML and JavaScript syntax checks passed; changed SCSS files compiled.
- Arabic catalogs passed `msgfmt --check-format`; no newly untranslated entries were found.
- Odoo database upgrades and browser suites were not rerun for this Git organization task. Earlier validation results remain in the feature records.
- Both classification polling race checks passed. Historical reference file sizes and SHA256 hashes matched their manifest. Whitespace in the original reference CSV and notes was preserved to retain those hashes.

## Current changes before commit:

- Record the reviewed commits and distinguish current checks from earlier implementation validation.

Files changed:

- `ab_website_sale_product/changelog.d/2026-10-05-commit-review.md`
