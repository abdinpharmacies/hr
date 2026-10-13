2a458f1 Alhassan Hossny 2026-06-22 ab_product_seo_enhancement/Feat: Adding SEO enhancment module for website products
- Added product classification, trusted source bundles, and guarded SEO copy generation.
Files changed: `__init__.py`, `__manifest__.py`, `models/product_seo_bulk_optimization.py`, `models/seo_assistant.py`, `tests/test_product_seo_enhancement.py`, `i18n/ar.po`, `i18n/ar_001.po`.

Current changes before commit:
- Reject malformed or product-name-only AI responses before writing SEO fields.
- Ask the assistant for only six descriptive SEO fields and distinct keyword phrases.
- Cover rejected and valid responses with mocked API tests and translate the error in both Arabic catalogs.
Files changed: `models/seo_assistant.py`, `tests/test_product_seo_enhancement.py`, `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/current.md`.
