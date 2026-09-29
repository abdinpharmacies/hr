# Product enrichment and SEO generation

The catalog-aware template layer is documented in [README_SEO_TEMPLATES.md](README_SEO_TEMPLATES.md). It adds fixed structures, versioned contracts, strict validation, protected regeneration proposals and pilot gates to this existing engine. See [SEO_TEMPLATE_IMPLEMENTATION_REPORT.md](SEO_TEMPLATE_IMPLEMENTATION_REPORT.md) for the real catalog findings and pilot results.

This extends `ab_website_seo_optimization` in place. It preserves existing assistant IDs, the Ready API importer/cache, translations, versions, review/publish actions, website component suggestions, and internal page/product optimization. External enrichment now creates reviewable drafts through the existing bulk-job model. It does not automatically publish generated descriptions or modify inventory, prices, barcodes, or product identities.

## Architecture

```text
Configured data sources → retained bulk files → local source/identifier index
                                             ↓
Product identity → exact matching → bounded fuzzy candidates → optional API fallback
                                             ↓
                        accepted facts + separate reference/safety evidence
                                             ↓
Persistent work item → ordered AI providers → SEO draft → evidence review → approve/publish
```

`services/catalog.py` declares capabilities and research metadata. `services/providers.py` implements normalization, matching, HTTP adapter protocols, grounded prompts, and response validation. `services/datasets.py` parses supported native formats. The existing `ab.seo.assistant` model owns configuration, credentials, quotas, health, retry policy and caches.

New models use underscore technical names:

| Model | Purpose |
|---|---|
| `ab_seo_pipeline`, `ab_seo_pipeline_step` | Editable product-domain chains and ordering |
| `ab_seo_dataset` | Download/import checkpoints, retained files, revision/checksum and manual verification |
| `ab_seo_source_record`, `ab_seo_source_identifier` | Independent provider records and indexed identities |
| `ab_seo_work_item` | Unique persistent product/job work, partial language results and resume state |
| `ab_seo_enrichment_fact` | Immutable field-level source/generated/unverified evidence |
| `ab_seo_provider_call` | Immutable operation, timing, status, error and fallback audit |
| `ab_seo_cache` | Expiring positive/negative lookups and generated content |

The full [provider matrix and research references](PROVIDERS.md) describe actual access modes. A configured record is not proof of live access. No provider is advertised as offering unlimited hosted generation.

## Setup and upgrade

1. Back up the target database and filestore. Install the manifest dependencies in the Odoo environment: `requests` and `ijson` (validation used ijson 3.5.1).
2. Perform a targeted upgrade using the normal service maintenance process:

   ```bash
   /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -c /path/to/config -d database -u ab_website_seo_optimization --stop-after-init
   ```

3. Restart the Odoo service using that environment. The upgrade creates additive models/fields/indexes, provider configurations, five editable pipelines, and a dataset cron. It reuses the existing bulk SEO cron. No hook, destructive cleanup, base upgrade, or production data migration is included.
4. In SEO Settings, review source licenses and commercial permissions, then import datasets. Dataset B requires separate commercial permission; its public availability does not grant that permission.
5. Configure provider endpoints, models, limits and keys. Enable **Allow Remote** only for providers whose API should be used. Local inference also requires a running compatible server and an installed model.
6. Assign website product categories to the Drug, Cosmetic, Supplement, Food or General pipeline. Explicit product type wins; otherwise category ancestry selects a pipeline, then the existing medicine flag, then General. An explicitly selected job pipeline overrides product routing.
7. Choose pipeline steps and sequence, AI mode, languages, batch limit and items per tick. Start the existing published-products bulk action.

Existing `noupdate` provider records retain their saved values. Fresh-install defaults use current endpoints and configurable models. Use **Apply Provider Defaults** explicitly when updating an old saved configuration. Runtime model discovery prevents unavailable Gemini/Groq/OpenRouter models from silently continuing. Old Hugging Face inference URLs are routed through its current compatible endpoint. Qwen regional/workspace endpoints remain configurable.

No environment variable is mandatory. **API Key Name** optionally names a service environment variable; a stored key takes precedence. Existing names include `GOOGLE_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `ALIBABA_QWEN_API_KEY`, `READY_API_KEY`, and `OPENFDA_API_KEY`. Configure an environment variable name for Cohere, Cloudflare or USDA, or enter the key in the masked manager-only field. Never put keys in dataset URLs. Cloudflare also needs Account ID and model-specific neuron cost settings. Restrict paid usage at the provider account as well as in Odoo.

## Bulk datasets

Use **Datasets → Create** with provider, actual release filename, revision/date, direct HTTPS file URL or an upload, and optional expected checksum. **Validate Dataset** checks configuration; **Queue Import** schedules processing. The cron validates file content during normalization. Invalid rows are counted; a wholly unusable file fails. Uploaded data and the original download are retained.

Raw files and normalized JSONL live under the database filestore in `seo_datasets/<dataset-id>/`. Back up this directory with the database. SHA-256 is always recorded; supplied SHA-256 or MD5 checksums are verified. Downloads use ETag/Last-Modified and resumable byte ranges when supported. An unchanged release is reused. Downloads have a configurable size cap; no arbitrary SQL dumps are executed.

Import uses 500-record ORM batches and a persisted file byte offset. A restart replays only an uncommitted batch; provider/source-ID uniqueness prevents duplicates. Archive expansion/nesting and XML entities are restricted. Normalization streams records but restarts its current file if interrupted; allow sufficient cron execution time and disk for large releases. Prefer source partitions when available. Sources without HTTP range support may require a longer download call.

| Source | Import format/workflow |
|---|---|
| Egyptian A/B | Native CSV/JSON, independent providers and provenance |
| DailyMed | Native SPL XML, ZIP and nested release ZIPs; choose full/daily/weekly/monthly files from the official page |
| openFDA label/NDC/cosmetic | **Sync Dataset** expands the official download manifest into queued partition imports; ZIP JSON `results.item` |
| RxNorm | Licensed monthly/weekly RRF ZIPs; RXNCONSO atoms, RXNSAT attributes/NDC/strength and RXNREL relationships; suppressed rows are archived in the index |
| DSLD | Native label JSON/ZIP; use a JSON prefix for an aggregate array export |
| Open Facts | CSV, TSV, JSONL/NDJSON, gzip and ZIP; native code/name/ingredient/nutrient fields |
| USDA | Native branded-food JSON defaults to `BrandedFoods.item`; configure another official collection prefix as needed |
| PubChem / ChEMBL | SDF/gzip, or structured JSON/CSV exports; scientific context stays separate |
| DrugCentral | Official structures TSV or structured JSON/CSV scientific exports; do not upload/execute its PostgreSQL database dump |
| EDA / GS1 / CosIng / CIR | Authorized/manual CSV or JSON evidence, source URL and verification note; no automated browser scraping |

**Incremental** is enabled by default and must remain enabled for multipart releases and updates. Disable it only for a complete standalone snapshot; completion then archives older indexed rows absent from that snapshot. Import monthly RxNorm snapshots before ordered weekly updates. Download authorization for licensed RxNorm releases is handled outside Odoo; upload the licensed file. Archived atoms, attributes and relationships remain auditable in raw files.

Set **Sync Interval Days** and **Next Sync At** to schedule a configured dataset URL. Version, URL and checksum must describe the selected release. Download landing pages are references, not automatically assumed to be files. **Rebuild Index** replays the retained normalized file. **Resume** continues a failed dataset from its available checkpoint.

Manual evidence example (a JSON array, filename `evidence.json`):

```json
[{"source_id":"registration-record-id","name":"Exact product name","manufacturer":"Exact manufacturer","registration":"registration-number","strength":"source strength","dosage_form":"source form","references":["official evidence URL"]}]
```

Use only facts actually visible in the source. Record verification through **Verify Manual Evidence**. Ingredient sources use `inci`/`name`, `cas`, `ec`, `functions`, `restrictions`, and `references`; they never verify a commercial product's registration.

## Matching and provenance

Identity priority is provider source ID, validated GTIN, NDC, RxCUI, registration, ingredient identifiers, exact normalized name/manufacturer, exact name/strength/form, then bounded fuzzy and ingredient/strength/form candidates. Conflicting supplied strength/form/manufacturer reject a candidate. Fuzzy candidates remain review evidence and cannot replace an exact match. Equal-scoring conflicting source records are ambiguous.

Optional product **Enrichment Identity** accepts JSON keys `source_ids`, `gtin`, `ndc`, `rxcui`, `registration`, `strength`, `dosage_form`, `cas`, and `inchi`. Source IDs are keyed by provider technical key. Barcode aliases are checksum-normalized. Name search uses indexed normalized names and bounded prefix candidates; it is deliberately conservative and may miss spelling variants.

Each field records value, provider/type, source ID/revision, URL/checksum, confidence, match method, retrieval/verification time and acceptance. Source A and B remain separate. Internal catalog facts have first priority. Non-Egyptian drug references and secondary medical facts are retained for review, not promoted automatically to Egyptian product claims. RxNorm concepts/strength/relations remain normalization context. Ingredient and adverse-event sources cannot supply marketing facts.

Generated fields record provider/model, prompt version, stable input hash and input evidence IDs. Cache keys include source revisions, model, endpoint and generation settings; equivalent sources can be reused across jobs while linking the current job's evidence. Model metadata and failed lookups are cached. **Purge Stale Cache** deletes only expired cache entries, never source or audit records.

## Sequential fallback and quotas

Data providers run in configured pipeline order and can fill still-missing accepted facts. AI providers run separately in order until one returns a usable draft. The next product starts at the beginning of the chain, skipping persisted exhausted/cooling providers without network calls. OpenRouter can additionally try newline-separated configured models.

Request counters cover every HTTP attempt, including retries and model discovery. UTC daily/monthly/minute windows, token reservations, lifetime token caps and optional model-unit budgets are enforced under provider row locks. Shared API accounts should use **Quota Group** pointing to one root provider. Configure a separate provider record per model where quotas differ. Zero configured limits mean no *local* cap, not unlimited vendor allowance. Unknown token usage retains a conservative reservation.

Timeouts, connection errors, 429 and temporary HTTP failures receive bounded exponential retries. Only delays up to two seconds occur inside a work-item call; longer waits become persisted cooldowns and immediate fallback. Authentication/permanent schema/model failures are not retried. Negative caching prevents repeated failures for the same input. If every generator is exhausted, the work item waits until the earliest available reset; it is not discarded after three daily-limit failures. Permanent all-provider failure is bounded and can be retried through the admin action.

Provider errors do not stop the catalog job. Architectural/programmer/database failures stop it with an error line and server trace. Logs store error categories/status codes, never request bodies or credentials. **Reset Usage** is manager-only and audited; use it only after checking the provider account. It does not erase lifetime token accounting.

## How a 100K-product enrichment job works

1. Starting a job records the domain, maximum product ID and count. The UI returns immediately; no remote request or 100K work-item creation happens in that HTTP request.
2. The existing cron discovers at most 500 product IDs at a time using an ID cursor. The snapshot upper bound excludes newly created products from that run.
3. Each `(job, product)` has one persistent work item. The worker uses local indexed data before any permitted API fallback.
4. It attempts the source and generator chains, saves per-field evidence, partial language results and a draft, then commits that item through Odoo's cron progress API.
5. A tick processes a configurable maximum (default 50) and stops after approximately 45 seconds between items. One in-flight bounded provider call may exceed that soft budget; configure timeouts to fit the server cron limit.
6. After a restart, the discovery cursor and committed items survive. Uncommitted work rolls back and is retried. Completed products are skipped. Unique source IDs, work-item keys, evidence hashes and cache keys prevent duplicate persisted results.
7. Review-required results count as processed drafts, not published content. Queue, processing, success, failure, skipped, review and per-provider quota/call counters remain visible.

The design is resumable for 100K selections; no live 100K throughput benchmark is claimed. Total duration depends on local dataset coverage, database size, source quotas and inference speed. Use **Sources Only** to collect evidence and conservative drafts without AI. **Generate Missing Content** preserves complete native content by language; **Generate Drafts** explicitly requests replacement drafts. Existing page/internal-only optimization remains available with enrichment disabled.

## Review and safety

Content is classified as `SOURCE_FACT`, `GENERATED_TEXT`, `INFERRED_TEXT`, or `UNVERIFIED_TEXT`. Structured unsupported medical facts are rejected. Detected unsupported medical prose is retained as unverified evidence and replaced in the draft with conservative product information. This validation is not a semantic proof that arbitrary generated prose is correct: every enrichment translation requires a reviewer, evidence notes and approval before the existing publish action can write native website fields. Editing reviewed content requires review again. Published versions retain enrichment provenance.

Outputs include title, meta description, short/long description, keywords, search phrases and optional bullets. Arabic uses the existing language/translation flow and RTL rendering; brand/scientific names remain intact. English is not regenerated by an Arabic-only job. Prices, stock, identifiers, regulatory approvals and medical advice are never written by this engine.

Company record rules cover jobs, work items, evidence, calls and SEO history. Source catalogs are shared reference data. Provider keys are manager-only and masked. No new public controller is introduced; the existing authorized component-suggestion route uses sequential grounded providers.

## Troubleshooting

| Symptom | Action |
|---|---|
| Local miss | Import the correct release, check dataset completion and identity; enable remote fallback only if intended |
| License review required | Record the selected release/service terms and permission; do not bypass Dataset B's commercial restriction |
| Unsupported model | Refresh available models, choose a supported model and update its quota configuration |
| Waiting for providers | Inspect cooldown/reset times, key status and per-provider call errors |
| Unusable/malformed data | Check native format, JSON prefix and release schema; failed rows and original file are retained |
| Dataset remains queued | Ensure cron workers are enabled and service filestore permissions/disk are sufficient |
| All results need review | Expected: automated enrichment is draft-only; review source evidence and record corrections |
| Job failed on server error | Fix the architectural error before Resume; do not repeatedly retry an integrity failure |
| Missing dataset file after restore | Restore `seo_datasets` with the matching database filestore |

## Verification

Use a disposable database with mocked network tests:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -c /path/to/test.conf -d isolated_database -u ab_website_seo_optimization --stop-after-init --test-enable --test-tags /ab_website_seo_optimization,/ab_product_seo_enhancement --workers=0 --max-cron-threads=0
```

Omit the extension tag if it is not installed. Tests cover registration/order, quota → temporary failure → success, retries/timeouts/429/authentication/malformed data, exact/fuzzy matching, imports, deduplication, resume, progress, cache reuse, manual/license gates, review/publishing, local AI, model fallback, company access and immutable provenance. Live provider accounts, commercial permissions, full production datasets and a local inference server require separate setup and are not represented by mocked success.
