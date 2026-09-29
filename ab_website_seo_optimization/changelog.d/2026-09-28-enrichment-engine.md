# Product enrichment engine — 2026-09-28

## Recent relevant commit

- Commit: `2a8b70f13edfe39f4b0ede54fb1090952eb2455e`
- Author: Alhassan Hossny
- Date: 2026-06-21
- Original subject: `ab_website_seo_optimization/Chore: Adding API from FBA and Drugs-EG, Edited the Single, Bulk SEO Optimization process and addedd Translation`
- Added Ready API/openFDA integration, website SEO suggestions, Arabic translations and updated single/bulk workflows.

Files changed:

- `ab_website_seo_optimization/__init__.py`
- `ab_website_seo_optimization/__manifest__.py`
- `ab_website_seo_optimization/controllers/__init__.py`
- `ab_website_seo_optimization/controllers/seo_component.py`
- `ab_website_seo_optimization/data/seo_assistant_data.xml`
- `ab_website_seo_optimization/i18n/ar.po`
- `ab_website_seo_optimization/i18n/ar_001.po`
- `ab_website_seo_optimization/models/__init__.py`
- `ab_website_seo_optimization/models/drug_eg_import_dashboard.py`
- `ab_website_seo_optimization/models/product_drug_data.py`
- `ab_website_seo_optimization/models/product_seo.py`
- `ab_website_seo_optimization/models/product_seo_bulk_optimization.py`
- `ab_website_seo_optimization/models/product_seo_optimize_confirm_wizard.py`
- `ab_website_seo_optimization/models/product_seo_translation.py`
- `ab_website_seo_optimization/models/seo_assistant.py`
- `ab_website_seo_optimization/scripts/download_drug_eg_data.py`
- `ab_website_seo_optimization/security/ir.model.access.csv`
- `ab_website_seo_optimization/static/src/js/seo_dialog_ai_patch.js`
- `ab_website_seo_optimization/tests/test_product_seo.py`
- `ab_website_seo_optimization/views/drug_eg_import_dashboard_views.xml`
- `ab_website_seo_optimization/views/menus.xml`
- `ab_website_seo_optimization/views/product_drug_data_views.xml`
- `ab_website_seo_optimization/views/product_drug_data_website_templates.xml`
- `ab_website_seo_optimization/views/product_seo_optimize_confirm_wizard_views.xml`
- `ab_website_seo_optimization/views/product_seo_views.xml`

## Current changes before commit:

- Move Allow Remote directly below API Key Name in the provider form so connection settings are together.
- Fit provider list columns to their longest visible value or heading, with horizontal scrolling and styles scoped to this list.
- Fix SEO screen crashes under Odoo XML development mode by formatting all enrichment view architectures with nonempty leading whitespace; add a file-loader and bilingual form regression test.

- Extend the existing provider model with source classes, metadata, licenses, local-first adapters, quotas, model discovery, retries, health and audit logs.
- Add source ingestion/indexing, independent Egyptian datasets, native SPL/RRF/SDF/JSON/CSV parsing, retained files/checksums and resumable imports.
- Add configurable domain/category pipelines and persistent product work items, sequential source/generator fallback, cache reuse, quota recovery and progress reporting.
- Generate grounded Arabic/English drafts with field provenance, mandatory evidence review and immutable published-version references.
- Preserve existing provider XML IDs, Ready API cache/importer and internal page/product workflows; correct Arabic internal generation context and fresh-install endpoint/model defaults.
- Extend existing admin views, mask credentials, restrict management operations and apply company rules to jobs/evidence/SEO history.
- Maintain both Arabic catalogs from the exported module POT; add mocked regression/acceptance tests and setup/provider documentation.

Files changed:

- `ab_website_seo_optimization/PROVIDERS.md`
- `ab_website_seo_optimization/README_ENRICHMENT.md`
- `ab_website_seo_optimization/VERIFICATION.md`
- `ab_website_seo_optimization/__manifest__.py`
- `ab_website_seo_optimization/changelog.d/2026-09-28-enrichment-engine.md`
- `ab_website_seo_optimization/controllers/seo_component.py`
- `ab_website_seo_optimization/data/enrichment_cron.xml`
- `ab_website_seo_optimization/data/enrichment_providers.xml`
- `ab_website_seo_optimization/data/seo_assistant_data.xml`
- `ab_website_seo_optimization/i18n/ar.po`
- `ab_website_seo_optimization/i18n/ar_001.po`
- `ab_website_seo_optimization/models/__init__.py`
- `ab_website_seo_optimization/models/enrichment_dataset.py`
- `ab_website_seo_optimization/models/enrichment_pipeline.py`
- `ab_website_seo_optimization/models/enrichment_provider.py`
- `ab_website_seo_optimization/models/product_seo_bulk_optimization.py`
- `ab_website_seo_optimization/security/ir.model.access.csv`
- `ab_website_seo_optimization/security/record_rules.xml`
- `ab_website_seo_optimization/services/__init__.py`
- `ab_website_seo_optimization/services/catalog.py`
- `ab_website_seo_optimization/services/datasets.py`
- `ab_website_seo_optimization/services/providers.py`
- `ab_website_seo_optimization/static/src/scss/seo_provider_list.scss`
- `ab_website_seo_optimization/tests/__init__.py`
- `ab_website_seo_optimization/tests/test_enrichment.py`
- `ab_website_seo_optimization/tests/test_product_seo.py`
- `ab_website_seo_optimization/views/enrichment_views.xml`
