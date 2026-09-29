# Catalog-aware SEO templates

This layer extends the existing enrichment queue, source index, assistants, translations, review actions and immutable SEO versions. It does not create another generation queue or publish automatically. The September 2026 catalog audit and verification results are in [SEO_TEMPLATE_IMPLEMENTATION_REPORT.md](SEO_TEMPLATE_IMPLEMENTATION_REPORT.md).

## Workflow

```text
Published, saleable product linked to ab_product
  → semantic template selection + category conflict checks
  → existing source pipelines and field-level evidence
  → normalized catalog/accepted source facts
  → fixed template structure
  → deterministic content or constrained AI wording
  → structural, factual, medical, metadata and duplicate validation
  → draft / preserved regeneration proposal
  → evidence review → existing approval/versioning → explicit publication
```

The existing website workflow operates on `product.template` records linked to `ab_product`. It does not create website products for the unsynchronized master catalog or publish unpublished products. A 100K batch limit does not change that eligibility rule.

## Templates and selection

Nine editable records are installed under **SEO Optimization → Settings → SEO Templates**. Each has a code, product type, source domain, priority, version, categories, semantic category names, product signals, ordered sections, fact requirements, metadata/keyword limits, language rules and generation instructions. Seed records use `noupdate`; upgrades preserve administrator configuration.

Selection is deterministic:

1. Explicit product SEO template.
2. Existing explicit enrichment type (`drug`, `supplement`, `cosmetic`, `general`); unsupported explicit types use General and raise a review flag.
3. Explicit category mapping, preferring the nearest assigned category over ancestors.
4. Exact normalized semantic category names, including slash-delimited legacy names, preferring the nearest category.
5. Catalog medicine flag, then product-name/attribute signals.
6. General Product fallback.

Priority and record ID break ties. Equal-specificity competing families produce an ambiguity flag. Name signals and the medicine flag also detect conflicts with category routing. They do not silently rewrite the taxonomy. A manager can resolve a wrong classification with **Explicit SEO Template** on the product, then regenerate. No prescription/OTC inference is performed.

For example, `Beauty & Skin Care → Hair Care` selects Hair Care. A tissue product under `Medicines → Ear Care` retains the auditable category decision but is flagged for review. The draft makes no treatment claim. Correct its template assignment before approval.

## Structure and facts

Every section has a stable key, translated heading, sequence, fact-key list and Required, Optional or Forbidden policy. Unknown or forbidden sections and incorrect ordering are rejected. A required section without facts is omitted and reported as missing; a required section with available facts cannot be omitted. Optional sections without facts cannot be filled with invented text.

The common factual sections are About the Product and Product Information. Medicine adds Active Ingredients and Strength, Form and Package. Supplements add Ingredients and optional Nutritional Information. Devices require Specifications when available. Other families can include source-backed Key Ingredients and Suitable For. Directions, Warnings and Storage are optional and evidence-dependent.

Facts come from catalog identity, supported single-valued attributes, manager-supplied enrichment identity, and the existing exact-match source pipeline. Literal strength/form/package fragments may be retained from the product name, with `catalog_name_literal` provenance. Concentration denominators are excluded from package extraction. No unit conversion or medical interpretation is performed. Existing marketing descriptions are not promoted to verified facts.

Clinical directions, warnings, indications, suitability and storage from remote sources retain the existing conservative Egyptian official/regulatory-source restriction. Foreign labels, ingredient research and adverse-event context do not establish Egyptian product claims. Unsupported source fields remain evidence rather than generation facts. Source conflicts lower confidence even when the conflicting row is unverified.

## Deterministic and AI generation

**Deterministic** is the default on bulk jobs and individual SEO records. It renders available facts in the template order, preserves identity, and uses translated connecting text. Missing facts remain missing. This is a factual baseline, not a substitute for richer source information.

**AI Wording** uses the existing pipeline's sequential generators when the pipeline permits generation and sufficient facts exist. The request contains product identity, category context, normalized facts, source provenance, the full template contract, validation rules and language. The response must contain only:

```json
{
  "meta_title": "...",
  "meta_description": "...",
  "short_description": "...",
  "sections": [{"key": "about_product", "content": "...", "fact_keys": ["name"]}],
  "keywords": ["..."]
}
```

The server supplies headings and renders escaped HTML. Section content must be extractive from its assigned facts. Metadata wording is limited to source vocabulary and a small set of safe connecting words; unknown factual wording is rejected. This intentionally trades expressive freedom for fact preservation. Arabic and English share the same facts, scientific names and identifiers. Different generated section structures across languages are rejected. AI wording always requires evidence review.

The generation cache includes the full contract and category context, as well as the existing facts, stable sources, language, model and endpoint settings. A changed template cannot reuse an incompatible cached draft.

## Validation and review

Default metadata rules are 15–70 characters for titles, 80–170 for meta descriptions, and at most five keywords. Limits are configurable within bounded ranges. Length problems are review warnings, not instructions to truncate or pad text.

Hard rejection covers malformed schema, wrong identity, unsupported factual wording/numbers, invented section facts, unknown or forbidden sections, wrong section order, unsupported keywords, keyword stuffing, unexpected HTML, oversized content, unsupported medical claims and prohibited certainty/endorsement claims. Guaranteed results, cure claims, unsupported doctor recommendations and unsupported clinical-proof/safety language cannot pass. Missing facts, short metadata, category/source conflicts and duplicate-content findings require review.

Indexed normalized hashes detect exact title, meta and description duplicates among drafts. Native website title/meta fields are checked within website/company scope. Four indexed shingle fingerprints select up to 100 near-duplicate candidates; similarity above the configured threshold (default 0.85) raises a review flag. A saturated candidate set also raises a review flag instead of silently asserting uniqueness. Masked fact fingerprints identify repetitive, fact-poor boilerplate within a template. Approximate similarity is not an exhaustive proof of uniqueness.

Translations display template/version, confidence, provider/model, generation date, structured sections, facts and validation details. Editing SEO text invalidates evidence review. The review action revalidates the current text; rejected content cannot be confirmed, approved or published, including force publication. Review notes must describe the evidence checked and any accepted warnings. Every generated translation requires human review, even when structural validation passes.

## Versioning and regeneration

Template/section edits increment the template version. Each work item stores bilingual contract snapshots and facts; each translation stores its own contract, version, structured output and provider/model. Approved versions retain an immutable template/fact/validation snapshot alongside existing source provenance and reviewer details. Stored outdated flags identify drafts generated from older template versions.

Bulk modes:

- **Generate Missing:** preserve approved/published/under-review SEO and complete draft languages; generate only missing languages.
- **Regenerate Selected:** generate within Selected Products or Selected Category.
- **Regenerate Failed:** filter to products with a failed work item.
- **Regenerate Outdated Templates:** filter to records whose stored template version is outdated.
- **Regenerate Using Selected Template:** generate products assigned to the selected template using its current version. Historical contracts remain in snapshots; this does not reactivate an old editable template revision.

Approved, published and under-review content stays intact. New output is retained on the work item. **Apply Regeneration Proposal** explicitly replaces the review draft after validation; approved versions and published website text remain until a new approval and publication. Legacy bulk optimization cannot overwrite reviewed or template-managed SEO.

## Dry run, pilot and bulk operation

1. Select 10 representative products and run **Dry Run**. It reports eligible count, an upper bound on translations to generate, per-category routing/counts, and up to 100 detailed product decisions: template/version, local matches, missing facts, conflicts, confidence, generate/skip/review decisions. It does not call remote providers or create drafts. Estimates outside the sample are explicitly bounded, not asserted as confirmed source matches.
2. Generate a deterministic pilot. Inspect both languages, actual facts, omitted sections and conflicts. Start with 10; expand to 50 or 100 through the same queue as needed. Correct template overrides and source facts before regeneration.
3. If evaluating AI, run a separate small AI pilot with configured providers. An AI pilot is required to unlock larger AI jobs; a deterministic pilot does not prove AI output quality.
4. Review every pilot translation. Apply and review any protected-content proposal if it is included. Record Pilot Review Notes, then use **Validate Pilot**.
5. Runs above 100 require a validated pilot with the same company, languages, generation mode and current template configuration. A template-filtered run requires coverage of that template; an unfiltered run requires all active templates. A changed template requires a new pilot.
6. Select category/products/template as needed, set the batch limit, select the validated pilot, and enqueue. The normal cron discovers at most 500 IDs at a time and processes persistent work items, committing progress through the existing cron transaction boundary. It does not materialize all products when enqueueing.
7. Use Resume Job after an interruption and Retry Failures for failed/provider-waiting items. Completed work is not repeated. Partial language results and evidence remain available. Job scope/settings cannot be changed after starting.

Provider quotas, model fallback, shared quotas and existing source/license controls are retained. Missing keys are marked as authentication unavailable and fallback continues. Temporary failures have bounded provider retries and persistent exponential-backoff scheduling; item retry waiting is bounded to eight attempts. Permanent failures do not receive endless retries. No new cron or external database write is introduced by the template layer.

The real pilot in the implementation report has intentionally **not** been approved by a human reviewer. The large-run gate remains closed for that pilot.

## Deployment and validation

Upgrade only `ab_website_seo_optimization`, then reload the application workers through the normal deployment process. Do not upgrade `base`. Testing used a database/filestore copy with cron disabled and HTTP/gevent ports 5069/5072; the live PyCharm-managed service was not restarted.

Development tests are retained as explicitly requested. Exclude development tests and bytecode when packaging a runtime-only production addon. The deployment must include the pre-existing uncommitted enrichment engine files as well as this template layer; installing only the newly added template files is insufficient.
