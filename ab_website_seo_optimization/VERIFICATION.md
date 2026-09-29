# Verification and delivery record

## Scope

Implemented in the existing `ab_website_seo_optimization` module, version `19.0.2.0.0`. No parallel addon, lifecycle hook, base upgrade or external database write was introduced. Unrelated working-tree changes were left in place.

## Executed checks

- Provider column layout: SCSS compilation, manifest parsing and XML parsing passed. A read-only Odoo registry check confirmed the scoped list class and backend stylesheet registration in `en_US` and `ar_001`. Browser visual verification was unavailable. Restart the running Odoo process to reload the manifest asset declaration, then refresh the browser; deployments without XML development mode also need a targeted module upgrade to load the inherited list class.
- Python compilation without writing bytecode: 27 module Python files passed.
- XML parsing: 19 module XML files passed; Odoo also loaded and validated the inherited views, security and data during targeted upgrades.
- Both Arabic catalogs passed `msgfmt --check-format`; all current exported POT strings have a translation. Existing msgids and unrelated translations were preserved.
- Targeted module upgrade repeatedly succeeded in `codex_seo_validation_20260928`, restored from an `ecom19` backup. Test cron workers were disabled.
- Mocked Odoo module and installed `ab_product_seo_enhancement` compatibility suite: 70 tests, 0 failures, 0 errors; one additional focused dataset-download restart test also passed (71 verified tests total).
- `git diff --check` passed for the module.
- Read-only upgrade audit preserved all 578 existing module XML IDs and all eight saved provider configurations. Existing SEO/job/history tables were empty and remained empty after test rollback.
- The upgraded copy has 30 seeded provider records, 31 adapter keys (including configurable Other), and 37 indexes across work items, source records/identifiers, cache and provenance.
- Arabic runtime menu verification: `Dataset Imports` (`en_US`) → `استيراد مجموعات البيانات` (`ar_001`).

## Required fallback acceptance

`test_acceptance_quota_failure_success_and_resume` uses three local-compatible providers and mocked HTTP:

1. A has already consumed its daily request allowance: no network request, quota state persists.
2. B receives 503 twice: bounded retry, then persisted cooldown.
3. C returns a valid grounded completion: the product reaches Review Required and the job continues/completes.
4. Exactly three HTTP attempts occur for the first product; native product SEO remains untouched.
5. Resuming does not repeat completed work or create duplicate provenance. Token accounting reflects the successful response.
6. A second product completes through C with one HTTP call while A remains exhausted and B remains in cooldown; the job reaches two processed products. This expanded acceptance case was rerun separately and passed.

The 100K configuration test verifies asynchronous enqueue with no network calls or eager work-item creation. Discovery uses bounded ID-cursor batches; each product has a unique persistent work item. Quota-wait, cache-reuse, company-access, review-gate and integrity tests exercise the other resume boundaries. This is architectural verification, not a live 100K throughput benchmark.

## Runtime and migration notes

- The running `ecom19` database was inspected read-only; it was not upgraded and no catalog enrichment/publishing was started there.
- `ijson` 3.5.1 was installed into the existing Odoo virtual environment for parsing and validation. Install it in every deployment worker environment.
- Apply the targeted module upgrade and restart through normal deployment before using the new fields/views in the running service. No separate data migration is required for the inspected database.
- New dataset cron runs once per minute; the existing bulk cron is reused. Cron workers must be enabled in the deployed service.
- No bulk release was downloaded into the live catalog, no API key was added, and no live provider or local inference server was used. Imported fixtures and mocked responses validate code paths only.
- Existing saved model/endpoint values are preserved. Review them in the UI and use Apply Provider Defaults or enter current account-specific settings before enabling remote requests.
- Import licensed datasets, assign categories/types, review source terms, configure account/model quotas and enable desired providers before starting a catalog job.
- The original database/filestore backup and validation logs were retained under `/tmp`; operational backups should use the normal durable backup location.

## Files changed

Every path below belongs to this addon. Full setup and architecture are in [README_ENRICHMENT.md](README_ENRICHMENT.md); the complete provider/access/quota/license matrix and official links are in [PROVIDERS.md](PROVIDERS.md).

- [PROVIDERS.md](PROVIDERS.md)
- [README_ENRICHMENT.md](README_ENRICHMENT.md)
- [VERIFICATION.md](VERIFICATION.md)
- [__manifest__.py](__manifest__.py)
- [changelog.d/2026-09-28-enrichment-engine.md](changelog.d/2026-09-28-enrichment-engine.md)
- [controllers/seo_component.py](controllers/seo_component.py)
- [data/enrichment_cron.xml](data/enrichment_cron.xml)
- [data/enrichment_providers.xml](data/enrichment_providers.xml)
- [data/seo_assistant_data.xml](data/seo_assistant_data.xml)
- [i18n/ar.po](i18n/ar.po)
- [i18n/ar_001.po](i18n/ar_001.po)
- [models/__init__.py](models/__init__.py)
- [models/enrichment_dataset.py](models/enrichment_dataset.py)
- [models/enrichment_pipeline.py](models/enrichment_pipeline.py)
- [models/enrichment_provider.py](models/enrichment_provider.py)
- [models/product_seo_bulk_optimization.py](models/product_seo_bulk_optimization.py)
- [security/ir.model.access.csv](security/ir.model.access.csv)
- [security/record_rules.xml](security/record_rules.xml)
- [services/__init__.py](services/__init__.py)
- [services/catalog.py](services/catalog.py)
- [services/datasets.py](services/datasets.py)
- [services/providers.py](services/providers.py)
- [tests/__init__.py](tests/__init__.py)
- [tests/test_enrichment.py](tests/test_enrichment.py)
- [tests/test_product_seo.py](tests/test_product_seo.py)
- [views/enrichment_views.xml](views/enrichment_views.xml)

## XML development-mode correction

The initial regression run did not enable `--dev=xml`. Compact view architecture tags exposed Odoo 19’s file loader assuming `field_arch.text` is a string; eleven enrichment views reproduced the reported `NoneType + str` crash. The enrichment XML was reformatted without changing its canonical structure or field values. All 38 module view records passed the actual Odoo file loader, and the new `test_enrichment_views_load_from_files` passed under `--dev=xml`, including English and Arabic combined SEO forms.

Read-only verification against the current `ecom19` database also passed `ab.product.seo.get_views` for list/form in both `en_US` and `ar_001`. No service restart or database update was needed for this formatting correction.
