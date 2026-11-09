# Match old website publication from an export

Commit: `339d5a323584e50001a3031002f3eceb04d2ca16`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_website_sale_product/IMP: restrict automatic product creation and publication`

- Established explicit publication control for linked website products.

Files changed relevant to this update:

- `models/ab_product.py`
- `models/add_many_by_codes_wizard.py`
- `models/website_product_sync_job.py`

## Current changes before commit:

- Add an administrator-only button to preview and apply publication matching from the old site's Published CSV or JSON export.
- Match uncoded legacy rows by a unique normalized name, and show missing or ineligible codes before applying.
- Reconcile all scoped `product.template` publication states, including unlinked products.
- Translate the new workflow in both Arabic catalogs and document the export steps.
- Update the website availability help to name both explicit publication workflows.

Files changed:

- `models/legacy_publication_import.py`
- `models/ab_product.py`
- `models/__init__.py`
- `security/ir.model.access.csv`
- `views/legacy_publication_import_views.xml`
- `tests/test_legacy_publication_import.py`
- `tests/__init__.py`
- `__manifest__.py`
- `i18n/ab_website_sale_product.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `README_website_product_sync.md`
- `changelog.d/2026-11-08-publish-by-codes.md`
- `changelog.d/2026-11-09-legacy-publication-import.md`

Validation:

- Nine focused import tests passed on the isolated database after targeted upgrades; the exporter passed `node --check`.
- Both Arabic catalogs passed `msgfmt --check-format`, and the import menu displayed in Arabic under `ar_001`.
- A targeted upgrade completed on local `ecom19`. A transaction-rolled-back preview of the supplied CSV reached `review` with 24,179 unique codes, 1,428 missing, 1,548 ineligible, and 10,052 to unpublish; no publication changes were applied.
