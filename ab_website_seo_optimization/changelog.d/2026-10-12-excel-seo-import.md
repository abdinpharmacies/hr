# Excel SEO draft import

Recent relevant commit: `69e7201` Mohamed Fawzy 2026-09-29 `ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow`.

Current changes before commit:
- Add an Excel template and manager-only import wizard for product SEO content matched by product code.
- Import English content by default into SEO translation drafts, including meta fields, descriptions, ingredient, warnings, contraindications and storage.
- Validate all rows and published product matches before writing; preserve existing optional values when spreadsheet cells are blank.
- Keep imported medical content in review drafts without writing native website fields or publishing.
- Accept numeric product-code cells, preserve text codes, and reset generation metadata when importing manual drafts so they can follow the existing approval workflow.
- Add Arabic UI translations and focused import and access tests.

Files changed: `__manifest__.py`, `models/__init__.py`, `models/product_seo_xlsx_import_wizard.py`, `views/menus.xml`, `views/product_seo_xlsx_import_wizard_views.xml`, `security/ir.model.access.csv`, `i18n/ar.po`, `i18n/ar_001.po`, `tests/__init__.py`, `tests/test_product_seo_xlsx_import.py`, `changelog.d/2026-10-12-excel-seo-import.md`.

Validation: 7 focused Odoo tests passed with 0 failures and 0 errors on `codex_seo_assistant_20261006`, using ports 5069/5072 with cron disabled. The ecommerce addons path was placed before the shared addons path to load this checkout's dependency. The targeted module upgrade, Python/XML checks, `git diff --check`, and both Arabic catalogs' `msgfmt --check-format` passed. Odoo POT references were merged for the import terms, and runtime menu, form and field labels were verified in `en_US` and `ar_001`. No live database upgrade was performed.

Import report UI follow-up:
- Match the image synchronization window's Configuration, Results and read-only report table layout.
- Keep the dialog open with Excel row, product code, product name, status and details, plus an action to open saved SEO drafts.
- Preserve the existing parser and import method. The UI wrapper runs the same import inside a savepoint and shows known validation failures in the report; a failed file reports no imported products and its parsed rows as not imported.
- Keep authorization errors as access errors, and clear old report feedback when the upload configuration changes.

Validation: 11 focused import and report tests passed with 0 failures and 0 errors on the same development database. Tests cover successful report links, rejected-file reporting without partial success, rollback after a late failure, invalid-file feedback and unauthorized report calls. English and Arabic report statuses, failure summaries and the resolved read-only table were verified at runtime. Both Arabic catalogs passed `msgfmt --check-format`. No live database upgrade was performed.
