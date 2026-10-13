# SEO pending review menu

Current changes before commit:
- Rename the Arabic Excel import label to `استيراد SEO من Excel` in both Arabic catalogs.
- Add a Pending Review menu beside All SEO Records for active draft, generated and under-review records, using existing model permissions and company rules.
- Add Ready to Publish for approved records and a Published SEO menu using the existing published action.
- Label the import report shortcut Review Imported Products; retain its restriction to the current import's saved records.
- Show imported/not-imported counts, including all parsed rows when a file is rejected without saving any rows.
- Group All Records, Pending Review, Ready to Publish and Published SEO under the existing All SEO Records tab. Clear the parent's old action on upgrade and retain existing workflow action/menu XML IDs.

Files changed: `views/menus.xml`, `views/product_seo_xlsx_import_wizard_views.xml`, `models/product_seo_xlsx_import_wizard.py`, `tests/test_product_seo_xlsx_import.py`, `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-10-12-pending-review-menu.md`.

Validation: XML parsing, menu/action references, the three-state domain, both catalogs' `msgfmt --check-format`, and whitespace checks passed. A targeted module upgrade passed on development database `codex_seo_assistant_20261006` with HTTP and cron disabled (configured ports 5069/5072). Runtime menu/action labels passed in English and Arabic after a module-scoped Arabic translation import with overwrite. No new automated tests were added for this menu-only change. No live database upgrade or browser layout check was performed.

Follow-up validation: 11 import tests passed with 0 failures and 0 errors on the same development database, including summary counts, report scope, rollback and unauthorized import access. Runtime checks passed for all three menu/action domains, English/Arabic labels, the review button and success-summary translation. Python/XML parsing, both Arabic catalogs and whitespace checks passed. The development replica logged existing missing-model and missing-filestore notices; no live database upgrade or browser layout check was performed.
