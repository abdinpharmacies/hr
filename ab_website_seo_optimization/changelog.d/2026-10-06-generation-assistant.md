# Generation mode and SEO assistant selection

## Recent relevant commit

- Commit: `69e72011cc12874ea2b3f3d65cd7390d9b614bf8`
- Author: Mohamed Fawzy
- Date: 2026-09-29
- Original subject: `ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow`
- Added template generation modes, source enrichment and reviewable SEO drafts.
- Relevant changes introduced the generation pipeline and template controls updated here.

Files changed: see the full module file list in `git show --name-only 69e7201 -- ab_website_seo_optimization`. Relevant files:

- `models/enrichment_pipeline.py`
- `models/seo_template_workflow.py`
- `views/seo_template_views.xml`
- `tests/test_enrichment.py`
- `i18n/ar.po`
- `i18n/ar_001.po`

## Current changes before commit:

- Disable SEO Assistant in deterministic mode on individual SEO records and enrichment jobs, preserving existing workflow state restrictions and saved selections.
- Carry the selected assistant into individual AI jobs and try it before the pipeline alternatives without duplicating providers. Empty selections retain pipeline ordering; Sources Only still prevents AI generation.
- Ignore saved assistants during deterministic generation, reject archived or non-generation assistants during AI execution, and prevent changing the assistant on started jobs.
- Move Website to the end of the individual SEO record's settings group.
- Add English explanations with Arabic translations in both catalogs.
- Render the deterministic explanation across both group columns so subsequent labels and values stay aligned; include the individual record's generation-mode selection references in both Arabic catalogs.
- Add nine regression tests for mode behavior, actual provider selection/fallback, invalid selections, job immutability, reader denial and compiled form behavior/order.

Files changed:

- `models/enrichment_pipeline.py`
- `models/seo_template_workflow.py`
- `views/seo_template_views.xml`
- `tests/test_enrichment.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-06-generation-assistant.md`

## Validation

- Isolated database: `codex_seo_assistant_20261006`, copied from the inactive historical SEO test database `codex_seo_templates_final_20260929`; no live database changes.
- Targeted SEO upgrade and module tests: 93 tests, zero failures/errors, exit 0. Odoo's statistics counter reports 99 including setup accounting; the result summary reports 93 executed tests.
- The historical test database initially lacked tables for newer installed website-product/storefront code. Upgraded only `ab_website_sale_product`, `ab_ecommerce_storefront` and `ab_website_seo_optimization` on the isolated copy; selected tests remained scoped to SEO.
- Validation settings: HTTP/gevent 5069/5072, HTTP disabled, workers 0, cron threads 0. Provider calls in regression tests were mocked.
- Exported the module POT before appending the three new messages. Both catalogs pass `msgfmt --check-format`.
- Runtime compiled forms under `en_US` and `ar_001` confirm translated hints, deterministic/AI editability and Website ordering.
- After the layout correction, the focused compiled-form regression passed (1 test, zero failures/errors; `/tmp/ab_seo_assistant_layout.log`). Runtime checks additionally confirm two-column hints and translated mode labels in individual and bulk forms.
- The copy lacks historical attachment files, producing attachment-read notices; these did not fail the tests. Browser visual verification was unavailable because no browser tabs were connected.
- Logs: `/tmp/ab_seo_assistant_final.log` and `/tmp/ab_seo_assistant_runtime.log`.
- Keep development tests out of runtime-only production packages. Applying this change to the running database still requires a targeted module upgrade and loading the updated Python code through the normal deployment process.
