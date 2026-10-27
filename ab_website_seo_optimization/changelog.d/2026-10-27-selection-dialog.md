# Existing SEO selection dialog and visible status

## Current changes before commit: selection follow-up

- Display a readable, translated SEO Status badge in a fixed 180px column instead of the narrow boolean checkbox. Keep the native product list unchanged.
- Enable the removable Without SEO Content filter by default in the single-product and bulk selection dialogs.
- When choosing an already-prepared product in the SEO form, offer Back to Product List or Open Product SEO before changing the field. Open the existing SEO record without creating a duplicate or regenerating content.
- Reopen the filtered product picker on return; closing the confirmation leaves the current selection unchanged. Ignore stale asynchronous selection results.
- Resolve the existing SEO record server-side without sudo. Require SEO membership and product read access; retain company and active-record checks, and match the exact website scope and catalog product identity used by the uniqueness constraint. Detect empty and incomplete drafts too; completion badges and content filters still describe completed content.
- Explain in both Arabic catalogs that an existing SEO record may still be a draft, so the user can open it before selecting a duplicate. Preserve the database uniqueness safeguard.
- Preserve the earlier bilingual-generation changes documented separately.

Files changed:
- `__manifest__.py`
- `models/seo_template.py`
- `static/src/js/seo_product_selector.js`
- `views/seo_product_selection_views.xml`
- `views/product_seo_views.xml`
- `views/seo_template_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_seo_selection.py`
- `tests/test_seo_product_selector.mjs`
- `changelog.d/2026-10-26-product-selection.md`
- `changelog.d/2026-10-27-selection-dialog.md`

## Validation

- Isolated database `codex_seo_selector_20261027`, copied from the inactive prior SEO test database; targeted SEO upgrade completed.
- 14 executed Odoo tests, zero failures/errors (including empty/incomplete drafts and exact website scope): translated fields/views, default-filter contexts, status width, existing-record navigation, company/website scope, ordinary SEO-user access and public denial.
- Eight JavaScript behavior checks using mocked services passed via `node ab_website_seo_optimization/tests/test_seo_product_selector.mjs`: new-product selection, confirmation, existing-record navigation, return to filtered list, dismissal, current-record selection, clearing and stale responses.
- Follow-up test log: `/tmp/seo-draft-selector-final.log`. Odoo POT export completed; both Arabic catalogs passed `msgfmt --check-format`. Runtime tests confirmed the Arabic badge labels. No browser visual verification was available.
- Historical attachment files are absent from the isolated clone; missing-file warnings did not fail the targeted tests.
- No running database upgrade, service restart, product edits or SEO publication performed.

## Recent relevant commit

- Commit: `b4567f07f57e8a766805831395ef67dbd6a44c98`
- Author: Mohamed Fawzy
- Date: 2026-10-13
- Original subject: `ab_website_seo_optimization/DOCS: record SEO generation changes and validation`
- Documented SEO generation feedback and pending-review navigation.

Files changed:
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`
- `changelog.d/2026-10-06-template-generation-feedback.md`
- `changelog.d/2026-10-11-product-button-feedback.md`
- `changelog.d/2026-10-12-pending-review-menu.md`
