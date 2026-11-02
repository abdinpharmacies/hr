# Legacy product SEO import

Commit: `a28adac1`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/FIX: allow admin deletion of staff users`

User-facing changes:
- Let administrators delete staff users and their linked tracking records together.

Files changed:
- `ab_ecommerce_storefront/models/staff_account.py`

Current changes before commit:
- Add an Import Old SEO button beside Sync Images in product list and kanban views.
- Preview code and website-product matches from the old site's JSON export before importing English and Arabic SEO drafts.
- Process matched rows in queued batches, preserve existing draft values, and retain per-row results and import history.
- Limit imports to SEO Managers and the selected company; keep Arabic UI translations in both catalogs.

Files changed: `__manifest__.py`, `models/__init__.py`, `models/legacy_seo_import.py`, `security/ir.model.access.csv`, `security/record_rules.xml`, `views/legacy_seo_import_views.xml`, `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-11-02-legacy-seo-import.md`.

Validation before deployment: Python and XML parsing, `git diff --check`, and both Arabic catalogs' `msgfmt --check-format` passed. Registry loading found both new models without upgrading the local database. The exported JSON contained 13,174 SEO language rows with no duplicate product codes. The remote database upgrade and runtime language checks are pending deployment.
