# SEO status in product selection

## Current changes before commit: product selection

- Add a read-only Has SEO Content column to the Search More product lists used by individual SEO records and bulk product selection.
- Add Has SEO Content and Without SEO Content filters with a removable Without SEO Content default filter in the SEO pickers, without changing the normal product list. The 2026-10-27 follow-up adds the wide status badge and existing-record dialog.
- Count only active SEO records with both a title and description in the same language. Empty records and archived records do not count; content in one language is sufficient and does not imply approval or publication.
- Compute status in a batch without sudo, using the current company, selected website (including global records), and existing record permissions. Restrict the supporting fields to SEO users.
- Add English source labels and Arabic translations in both catalogs.
- Earlier uncommitted generation changes are documented separately in `2026-10-26-bilingual-generation.md`.

Files changed:
- `__manifest__.py`
- `models/seo_template.py`
- `views/seo_product_selection_views.xml`
- `views/product_seo_views.xml`
- `views/seo_template_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_seo_selection.py`
- `changelog.d/2026-10-26-product-selection.md`

## Validation

- Targeted module upgrade on isolated `codex_seo_languages_20261026`: eight executed tests, zero failures/errors.
- Checks cover blank records, populated/archived records, same-language completeness, website scope, normal-user company isolation, denied public reads, scoped list/search views and runtime Arabic labels.
- Odoo POT export completed; both catalogs passed `msgfmt --check-format`. XML/Python parsing and `git diff --check` passed.
- No live database upgrade or service restart. Historical filestore attachments are absent from the isolated database copy; the missing-file warnings did not fail these tests.

## Recent relevant commit

- Commit: `b4567f07f57e8a766805831395ef67dbd6a44c98`
- Author: Mohamed Fawzy
- Date: 2026-10-13
- Original subject: `ab_website_seo_optimization/DOCS: record SEO generation changes and validation`
- Documented SEO workflow feedback and pending-review navigation.

Files changed:
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`
- `changelog.d/2026-10-06-template-generation-feedback.md`
- `changelog.d/2026-10-11-product-button-feedback.md`
- `changelog.d/2026-10-12-pending-review-menu.md`
