# Website Sale Product change log

## Recent commits

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

## Current changes before commit:

- Store every readable customer source row for staff review without creating accounts or codes.
- Open the latest completed batch from Eplus Stock and show stored customer rows in its All Customers tab.
- Automatically hide only fully identical source rows; keep rows with different values visible even when their reference or phone matches.
- Preserve existing code eligibility checks, add scoped access controls, Arabic UI text, documentation, and tests.

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
- `ab_website_sale_product/views/legacy_customer_views.xml`
- `ab_website_sale_product/views/legacy_customer_button.xml`
