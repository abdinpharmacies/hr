# Product classification implementation and deployment

Status: **installed in `ecom19`; all 77 taxonomy bindings ready as of 2026-10-04**. The classification implementation belongs to `ab_website_sale_product`; `ab_ecommerce_storefront` connects the need menu to category-based shop filters. The targeted upgrade and explicit category preparation were applied. The queue runner was activated on 2026-10-04 to process the user-started website classification run after its first job was found pending.

## Entry point and workflow

Open the existing **eCommerce Categories** page at `/odoo/ecommerce-categories` and select **Classify Products** (Arabic: تصنيف المنتجات). The inherited list header opens the client action `ab_website_sale_product.action_product_classification` at `/odoo/ecommerce-product-classification`. Existing category list/form views and CRUD remain owned by `website_sale`.

The page shows live ORM counts, progress, outcomes by primary category, current batch, last product, and run history. It polls through Odoo's authenticated `orm` service every three seconds. It has no public classification controller and does not keep a classification HTTP request open.

Website scope means active, saleable `product.template` records shared with or assigned to the selected website, including unpublished products and templates without an Abdin link. All Abdin Products includes inactive `ab_product` records. No branch stock, price, inventory, or external database data is modified. Product membership is collected in background chunks, bounded by the highest source ID when the run starts; changes to source eligibility during preparation can change the final snapshot count.

Start selects new, uncategorized products with no completed classification attempt and enqueues preparation, returning a run ID. Existing categorized products and prior classified, review, failed, ignored, manual, or forced decisions are excluded. An explicit Reset Manual Decision permits another attempt. A Start with no eligible products is rejected without creating a run. Eligibility is checked again during background snapshot preparation. Processing commits at most 250 products per queue transaction, with a 40-second soft checkpoint budget (an in-flight research request can extend it). Each product has a savepoint. Transaction serialization/deadlock errors roll back the checkpoint and use the queue's retry mechanism. Product-specific errors become failed results while other products continue. Completed products remain committed and are not reprocessed when a run resumes.

Pause/Stop apply between checkpoints. When a checkpoint holds the run lock, the control request becomes a high-priority job on the same queue channel. Resume skips completed rows. Start/Resume return a retry message instead of waiting for a busy catalog lock. New runs do not retry old failed or review products. Those results remain in their original run, accessible through Run History. Use the existing review/force workflow to resolve them.

## Live catalog coverage

The always-visible current catalog panel polls every three seconds independently of run progress. Website coverage is the count of eligible website products with at least one actual eCommerce category divided by the current eligible population. This includes existing categories outside the approved taxonomy. For All Abdin Products, linked template categories are used; an unlinked Abdin product counts as categorized when it has a non-ignored saved category assignment. Empty scopes show 0%.

New uncategorized products increase the denominator immediately on the next refresh. The display truncates to two decimal places so a small shortfall never rounds up to 100%. The separate run-processing bar remains a historical measure of attempted rows, including review/failure outcomes. Ready for classification counts never-attempted uncategorized products plus explicit resets. Ordinary Start never retries old review or failed rows. Changing scope or website selects that scope's latest run.

Coverage and eligibility use ORM relational domains and counts rather than reading all product IDs into Python. Classification history and assignment relations are administrator-only. No catalog classification or external research is triggered by dashboard polling.

## Persistent models

| Model | Purpose |
| --- | --- |
| `ab_product_classification_taxonomy` | Closed approved definitions, translated names, and explicit website category bindings. |
| `ab_product_classification_run` | Scope, source cursor, lifecycle, checkpoints, counters, requester/company, queue identity and errors. |
| `ab_product_classification_result` | One row per product/run, original facts and processing evidence, historical paths, research sources, confidence and current review outcome. |
| `ab_product_classification_assignment` | One current primary assignment or permanent ignore decision per product. |
| `ab_product_classification_review` | Append-only accept, ignore and manual-reset decisions with reviewer and timestamp. |
| `ab_product_classification_research` | Persistent query/provider/domain cache, including unsuccessful attempts. |

The abstract `ab_classification_audit` guards audit creation/writes against direct RPC/import changes. Workflow methods perform authorization before private internal writes. Runs/results/reviews have company record rules. Access is restricted to `base.group_system`, matching the existing module's administrator-operated synchronization. Catalog taxonomy, assignments and research are global catalog metadata available only to administrators. No branch-level role is granted classification access.

## Taxonomy preparation

The approved tree has **8 roots and 69 children**, with no third level. Definitions are seeded into the taxonomy model; installation does not seed or import website categories. Classification and synchronization never create categories.

1. Use **Prepare Taxonomy** on the progress page.
2. A unique exact match, or a unique recognized alias under the correct parent, is reused with its original ID. Reused aliases receive the canonical English name. When no suitable category exists in the expected branch, the explicit setup action creates the approved node and retains any similarly named records elsewhere.
3. Multiple suitable matches require administrator selection in **Taxonomy Bindings**. Select the intended shared website category and correct its English name and parent if needed. For a child, the parent must be the website category bound to its approved root. Bound categories must be shared across websites (`website_id` empty).
4. Run **Prepare Taxonomy** again to verify readiness and apply Arabic names. All 77 bindings must be ready before starting.

Setup does not automatically merge or delete legacy categories, reparent ambiguous records, or rename unrelated records. Once established, a binding cannot be redirected to a different record through the classification UI; correct the linked category itself. Bindings cannot be changed while a run is active. Existing unrelated and legacy category records can remain in the website; the classifier's assignment targets are the closed approved tree only.

## Category descriptions and Shop by Need

Open **Taxonomy Bindings** from the classification console, or `/odoo/approved-taxonomy-bindings`. Both **Category Description** and **Shop by Need** are editable columns; the row form offers the same fields. **Category Descriptions** at `/odoo/shop-category-descriptions` filters the table to the eight main categories. English and Arabic default descriptions are supplied for those roots and synchronized to their linked website category descriptions.

The ten approved needs are available on every taxonomy node. Selecting a need on a main category includes products in its descendants. Selecting it only on a subcategory includes products within that subcategory, without requiring a main-category selection. Products display the union of needs linked to their assigned categories and ancestors. The derived product field is read-only; administrators maintain its category links in the bindings table.

Initial links are on Skin Treatment (acne, brightening, anti-aging), Moisturizers (dry and sensitive skin), Sun Care (sun protection), Hair Loss & Scalp Care (hair loss and dandruff), Multivitamins (immune support and energy), and Sports Nutrition (energy). Administrators can adjust these broad category mappings. This does not infer an individual product's treatment indications.

The storefront menu uses stable `/shop?need=<key>` links and retains the filter during pagination, search and category browsing. Products must already belong to a mapped category for inclusion; an empty mapped category produces an empty need page. Existing product categories and stock/pricing values are not changed by need configuration.

## Classification evidence and synchronization

The pipeline is manual decision, historical mapping, deterministic local rules, optional web evidence, then review. Contradictory historical mappings are held for review instead of being silently overridden by a lower-priority stage.

The four historical source files are included byte-for-byte under `docs/reference/website_ecommerce/categories/`, with an accompanying README and SHA256 manifest. The bundle contains 24,216 variant rows, 385 historical category rows and 18,574 relations. E-plus codes join current products to historical templates; historical IDs never become current record IDs. Promotional and brand-only paths are not taxonomy definitions. The parsed evidence index is cached per worker process. No historical CSV is imported into live categories.

`services/classification.py` replaces the original keyword engine. Sync calls the same service. Rules use whole terms, keyword combinations, exclusions, priorities and explicit pharmaceutical context. `ORAL DROPS` is pharmaceutical evidence; `ORAL` alone is not Oral Care. Generic cream alone is unresolved, and recognized medicinal ingredients plus topical form take priority over cosmetics. The actual product card fields supply ingredients, concentration, manufacturer, groups, scientific groups, usage cause and usage manner; template attribute values are included where present. The medicine flag alone is not decisive because its model default is true.

Only one primary category is written. Existing product tags are not repurposed as primary categories; matched terms and structured data remain in the evidence JSON. Manual review preserves original processing evidence and appends a decision log. **Accept as Manual** approves the proposed or changed category permanently. **Reject / Ignore** preserves current website categories and prevents future automatic assignment; it remains visible as an ignored result. **Reset Manual Decision** explicitly permits re-evaluation on the next run.

Synchronization checks the persisted assignment before fallback rules. Manual and automatic assignments survive synchronization, including a product-name change; re-evaluation requires explicitly resetting the decision before starting a new run. Unknown fallback no longer creates Everyday Essentials or clears existing categories. Existing category selections without an explicit approval record are not assumed to be manual decisions; approve them through the review workflow to establish precedence.

Input fingerprints and `ENGINE_VERSION` permit reuse of unchanged successful results. Increment `ENGINE_VERSION` whenever classification rules, historical mappings, or the reference bundle change, and restart workers so the cached reference index reloads. Every reused result links to its original run result.

## Force categorization

The completed-run console has two controls:

1. **Review Suggestions** opens a selectable table with current website categories, a suggested approved category, evidence reason, score, and editable **Review Category** override. Select rows and use **Apply Selected Suggestions**. A selected row without a suggestion requires an explicit override.
2. **Automatically Assign All Review Products** opens a dialog showing the remaining review count and a required **Fallback Category**. It snapshots the non-ignored review rows, uses each override or available suggestion, and assigns the chosen fallback to rows without a suggestion.

Suggestions first use a single specific historical category, then a matching existing deterministic rule, an existing approved website category, a category alias in the matching main-category branch, or the Medicines main category when the medicine flag and dosage form support it. Other rows require an override or the chosen fallback. This workflow does not call an LLM or an external research provider. The score ranks available evidence; it is not a calibrated probability. Overrides and fallback assignments receive a zero evidence score rather than fabricated certainty.

Force changes use the existing integration queue in batches of 100. The console shows live force totals, applied/skipped/failed counts and a **Force Progress** view. A stop action retains already committed changes. Duplicate and obsolete queue jobs do not repeat application. Classification starts/resumes and taxonomy changes are blocked during an active force operation.

Existing manual, ignored and already forced assignments are preserved. Explicit force decisions use the `forced` assignment mode and survive ordinary classification and synchronization. The existing reset action permits later automatic re-evaluation.

Each applied change saves the old result state, assignment metadata and actual category IDs in the append-only review audit. Open **All Results**, filter **Force Categorized**, select rows and use **Undo Selected Force Changes**, or undo from a product result form. Undo runs through the same queue and restores saved values only when the force decision is still current; later manual decisions or category edits are retained and counted as skipped.

Validation on 2026-10-04: all 78 existing tests passed, a temporary browser test verified the two controls, fallback dialog, evidence columns and selected-apply action, and transactional checks covered non-superuser administrator access, public-user denial, main/selected application, overrides, fallback, preserved decisions, undo, later edits, batch bounds, stale jobs and idempotence. Both Arabic catalogs passed format validation. Live fields, dialog/filter translations, queue registration and suggestions were verified read-only after the targeted module upgrade. No live force batch was started by this implementation task; the user chooses the preview selection or automatic fallback in the UI.

## Queue deployment configuration

The manifest depends on the already-used `integration_queue_job` addon. Do not install the separate `queue_job` addon alongside it. Registered functions are `_process_checkpoint` and `_apply_control`; both use `root.classification`.

Enable `integration_queue_job` in the deployed Odoo server-wide `--load` list (preserving existing entries), set an explicit database, and configure the runner's HTTP destination to reach that same Odoo process. This repository's runner defaults its destination port to 8069, so explicitly set the actual deployment port.

Example environment settings, substituting the deployment's real host and port:

```text
ODOO_QUEUE_JOB_CHANNELS=root:1,root.classification:1
ODOO_QUEUE_JOB_HOST=127.0.0.1
ODOO_QUEUE_JOB_PORT=<actual Odoo HTTP port>
ODOO_QUEUE_JOB_SCHEME=http
```

The shared runner can also execute unrelated jobs already queued in that database; activation is an operator deployment step, not part of module installation. The module does not start a new worker framework or activate the live runner automatically.

The local `ecom19` instance is configured in `odoo19.conf` as follows. The existing startup modules are retained, the runner is bound to this database by the existing `db_name` setting, and its destination is the same Odoo instance:

```ini
server_wide_modules = base,rpc,web,integration_queue_job
queue_job_channels = root:1,root.classification:1
queue_job_scheme = http
queue_job_host = 127.0.0.1
queue_job_port = 4092
```

Restart the Odoo master after changing these settings. Verify `queue job runner ready for db ecom19` and successful `/queue_job/runjob` requests in the server log. The previously pending job is picked up automatically; do not create a duplicate classification run. A copy of the original local configuration and a snapshot of the 31,255 current product category assignments were retained under `/tmp` before activation. The local config remains outside Git because it contains deployment secrets.


Keep scheduled actions enabled for **Recover interrupted product classification**. It runs every five minutes and requeues classification/control jobs stuck in `started` for more than ten minutes only when their run is not actively locked. It also exposes failed queue jobs on the run and repairs missing continuation jobs. It does not alter unrelated queue functions. The queue's existing collector handles stale `enqueued` jobs.

Upgrade only `ab_website_sale_product` after deploying the code. Do not upgrade `base`. Then resolve taxonomy bindings and verify the queue runner before starting the catalog run.

## Web research configuration

`WebResearchProvider` is the isolated service interface. The supplied optional implementation uses the [Brave Web Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/codes), with no LLM and no page scraping in Odoo models.

Administrators configure these system parameters:

| Parameter | Value |
| --- | --- |
| `ab_classification.brave_api_key` | A valid Brave Search API subscription token. |
| `ab_classification.trusted_domains` | Comma-separated hostnames of approved official manufacturers or reputable pharmacies/retailers. Hostnames only, without URL schemes or paths. |

Research sends an exact-name query plus available manufacturer. Returned HTTPS sources must match an approved domain and all normalized product-name tokens before their titles/snippets are accepted as evidence. Deterministic rules map the evidence into approved nodes. Conflicting evidence remains unresolved. Original source URLs, titles, snippets, query, provider and timestamp are saved. Successful/empty results are cached for 30 days; configuration/network failures for one hour. Changing the provider or trusted domains changes the cache key.

Without either parameter, unresolved products become needs-review with a configuration message; the rest of the run proceeds. Local and historical matches never call the provider. Live Brave credentials and external research results were not available for this task: provider behavior was tested with explicit fixtures, including failure and persistence. Production source quality and coverage require validation after configuration.

## Verification

Initial classification validation used the isolated database `ab_classification_test_20260930`. The description/need update used the new isolated database `ab_taxonomy_needs_test_20261004` and alternate ports. Live category metadata was inspected and explicitly repaired in `ecom19` after validation.

- Fresh module installation succeeded, including its declared integration queue dependency.
- Full module suite on 2026-10-01: **77 tests passed, 0 failures, 0 errors**. It covers deterministic/historical rules, manual preservation, research/cache behavior, failure isolation, checkpoint reuse, real queue serialization/recovery, busy control requests, security, category counts, legacy synchronization, and the browser entry/progress/control flow.
- Final nonblocking Start/Resume check and browser control rerun: **2 tests passed, 0 failures, 0 errors** after that concurrency change.
- `node ab_website_sale_product/tests/check_classification_polling.cjs` checks that stale successful and failed requests cannot replace newer progress or errors.
- An actual integration runner processed 501 known-product fixtures asynchronously: **501 classified, 0 review, 0 failed, 501 unique result rows**. Four queue jobs completed: preparation, 250 products, 250 products, one product. Recorded job execution time totaled 3.279 seconds. This measures local rules on unlinked Abdin test products, not full-catalog or web-research throughput.
- Odoo-exported POT was used to maintain 261 classification entries in both Arabic catalogs without replacing unrelated translations. Both passed `msgfmt --check-format`. Runtime `ar_001` action, taxonomy and website category names differed from English as expected.
- Python/XML syntax, bundled source checksums, and `git diff --check` passed. Browser asset loading and controls were verified with Odoo's headless Chrome test support.

On 2026-10-04, a clean installation passed **78 tests with zero failures/errors**, including the browser console flow. Focused transactional checks verified alias reuse, wrong-branch preservation, inherited and child-only needs, public filtering, permissions and idempotence. Both Arabic catalogs passed format checks, and runtime descriptions, field labels and menu translations were verified. Live repair retained all 431 existing category records and parent relationships, created 25 missing approved nodes, and made all 77 bindings ready. Eight descriptions and initial links on six subcategories were saved. Live Arabic need pages, pagination and the category assurance-strip exclusion were checked.

No live paid provider call or completed full production catalog run is claimed. The local queue runner is now active and processing the user-started run. At 2026-10-04 12:26:18 UTC, its 31,255-product snapshot was complete and 4,250 products had been processed: 3,494 classified, 756 needing review, zero failures. Optional Brave credentials/domain policy remain operational setup tasks. Automated tests remain in the repository because the feature request explicitly requires them.

## Changed files

All paths below are relative to `ab_website_sale_product/`:

```text
__manifest__.py
models/__init__.py
models/ab_product.py
models/product_classification.py
models/shop_need.py
models/classification_force.py
services/__init__.py
services/classification.py
services/historical.py
services/web_research.py
data/classification_taxonomy.xml
data/shop_needs.xml
data/classification_queue.xml
security/ir.model.access.csv
security/classification_rules.xml
views/product_classification_views.xml
views/classification_force_views.xml
views/ab_product_views.xml
views/product_template_views.xml
static/src/js/product_classification.js
static/src/xml/product_classification.xml
static/src/scss/product_classification.scss
i18n/ar.po
i18n/ar_001.po
tests/__init__.py
tests/test_product_classification.py
tests/test_classification_ui.py
tests/check_classification_polling.cjs
tests/test_website_category_mapping.py
tests/test_website_product_sync.py
docs/classification_plan.md
docs/classification.md
docs/reference/website_ecommerce/categories/README.md
docs/reference/website_ecommerce/categories/manifest.json
docs/reference/website_ecommerce/categories/notes.md
docs/reference/website_ecommerce/categories/ecommerce_products.csv
docs/reference/website_ecommerce/categories/ecommerce_categories.csv
docs/reference/website_ecommerce/categories/ecommerce_product_category_rel.csv
changelog.d/2026-10-01-product-classification.md
```
