# Catalog-aware SEO templates

## Recent relevant commit

- Commit: `2a8b70f13edfe39f4b0ede54fb1090952eb2455e`
- Author: Alhassan Hossny
- Date: 2026-06-21
- Original subject: `ab_website_seo_optimization/Chore: Adding API from FBA and Drugs-EG, Edited the Single, Bulk SEO Optimization process and addedd Translation`
- Added source-provider integration, single/bulk optimization and Arabic translations that the existing enrichment engine extends.

Files changed in that commit:

- `__init__.py`, `__manifest__.py`
- `controllers/__init__.py`, `controllers/seo_component.py`
- `data/seo_assistant_data.xml`
- `i18n/ar.po`, `i18n/ar_001.po`
- `models/__init__.py`, `models/drug_eg_import_dashboard.py`, `models/product_drug_data.py`, `models/product_seo.py`, `models/product_seo_bulk_optimization.py`, `models/product_seo_optimize_confirm_wizard.py`, `models/product_seo_translation.py`, `models/seo_assistant.py`
- `scripts/download_drug_eg_data.py`, `security/ir.model.access.csv`
- `static/src/js/seo_dialog_ai_patch.js`, `tests/test_product_seo.py`
- `views/drug_eg_import_dashboard_views.xml`, `views/menus.xml`, `views/product_drug_data_views.xml`, `views/product_drug_data_website_templates.xml` (removed), `views/product_seo_optimize_confirm_wizard_views.xml`, `views/product_seo_views.xml`

## Current changes before commit:

- Audited the real 103,492-product master catalog, 32,510 website products and 423-category hierarchy before selecting nine template families.
- Added editable, versioned template/section records, nearest-category selection, explicit overrides and taxonomy conflict warnings without changing categories.
- Integrated fixed bilingual structures, fact-grounded deterministic/AI generation, metadata/medical/duplicate validation and auditable confidence into the existing enrichment queue.
- Preserved approved content as regeneration proposals and blocked legacy overwrites of reviewed/template-managed product SEO.
- Added missing/selected/failed/outdated/template regeneration modes, bounded dry-run reporting and reviewed-pilot gates for runs above 100 products.
- Preserved sequential provider/model fallback; missing keys now record authentication failures and temporary work-item retries are bounded.
- Added 25 template regression tests; the complete 97-test suite passed. A 29-product real-catalog pilot produced 58 unpublished outputs and preserved native/approved content.
- Appended the exported new UI strings to both Arabic catalogs. Updated operating documentation and the A–H implementation report.
- These changes extend pre-existing uncommitted enrichment files; that earlier work is recorded separately in `2026-09-28-enrichment-engine.md`. No unrelated module changes were included.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/seo_template.py`
- `models/seo_template_workflow.py`
- `models/enrichment_pipeline.py`
- `models/enrichment_provider.py`
- `services/seo_templates.py`
- `services/providers.py`
- `data/seo_templates.xml`
- `security/ir.model.access.csv`
- `views/seo_template_views.xml`
- `tests/__init__.py`
- `tests/test_seo_templates.py`
- `tests/test_enrichment.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`
- `SEO_TEMPLATE_IMPLEMENTATION_REPORT.md`
- `changelog.d/2026-09-29-seo-templates.md`
