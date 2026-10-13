# SEO Architecture and Roadmap

Project intent from AGENTS.md, not proof that every described feature exists. No ab_product_seo directory was present in the inspected ecommerce checkout. Verify actual code and ownership before implementation. Roadmap phases, 100-product batches and identity-key examples are starting proposals. Historical catalog counts in the RAG discussion must not be treated as current. The lifecycle lists state vocabulary: rejected/archived are branches/outcomes, not required steps after every publication. Explicitly protect approved descriptions from product-sync overwrites.

### Strategic Conclusion

Ready API is no longer the primary value source. E-Plus/B-Connect already contains enough structured pharmaceutical data to build a professional internal SEO platform.

First business value is not AI, Ready API, or RAG. First business value is:

- Populate native Odoo SEO fields correctly.
- Govern review and approval of pharmacy SEO content.
- Publish approved Arabic and English SEO content safely.


### Existing Ecommerce Boundary

`ab_website_sale_product` already synchronizes `ab_product` into native `product.template`.

It already owns:

- Product template creation and update.
- Product name and code sync.
- Price and cost sync.
- Sale/purchase flags.
- Active state.
- `description`
- `description_sale`
- `description_ecommerce`
- `website_description`
- `is_published`
- Public categories.
- Product tags.
- Images.
- E-Plus stock snapshots.

`ab_product_seo` must not duplicate this functionality. It should govern approved SEO content and publish into native Odoo fields after review.

### Native Odoo SEO Fields

Odoo 19 already provides:

- `website_meta_title`
- `website_meta_description`
- `website_meta_keywords`
- `website_meta_og_img`
- `seo_name`
- `description_ecommerce`

Odoo already handles:

- Canonical URLs.
- OpenGraph.
- Twitter cards.
- `hreflang`.
- Sitemap.
- Product JSON-LD.
- Breadcrumb JSON-LD.

The SEO module must populate and govern these fields, not replace Odoo website SEO rendering.

### `ab_product_seo` Ownership Rules

`ab_product_seo` owns:

- SEO content lifecycle.
- SEO drafts.
- Arabic and English SEO content.
- Review workflow.
- Approval workflow.
- Publishing decisions.
- Versioning.
- Rollback.
- SEO publish logs.
- SEO audit logs.
- Enrichment tracking.
- Future AI/RAG readiness.

`ab_product_seo` does not own:

- Product master data.
- Stock quantities.
- Pricing.
- E-Plus synchronization.
- Website product synchronization.
- Product image synchronization.
- Automatic publishing of medical content.

### Required Workflow

Use this lifecycle:

```text
draft
-> generated
-> under_review
-> approved
-> published
-> rejected
-> archived
```

Generated pharmacy content must remain reviewable. No medical claims may be auto-published.

### Recommended Roadmap

Phase 1: `ab_product_seo` core framework only.

- Models.
- SEO records.
- SEO translations.
- SEO versions.
- SEO publish logs.
- SEO audit logs.
- Review workflow.
- Approval workflow.
- Publishing into native Odoo SEO fields.

Phase 2: internal SEO generator.

- Generate SEO drafts from internal product/E-Plus data:
  - Product name.
  - Scientific name.
  - Manufacturer.
  - Origin.
  - Usage.
  - Product group.
  - Notes.

Phase 3: Arabic SEO.

- Arabic meta title.
- Arabic meta description.
- Arabic short description.
- Arabic FAQ.
- Arabic public description.

Phase 4: queue architecture.

Use `queue_job` / `integration_queue_job`.

Pipeline:

```text
Snapshot
-> Generate
-> Review
-> Publish
```

Recommended batch size:

```text
100 products/job
```

Recommended identity key:

```text
seo_product_<product_id>_<lang>
```

Phase 5: Ready API pilot only.

- Test 100 products.
- Measure match rate.
- Measure data quality.
- Measure Arabic quality.
- Measure scientific data quality.
- Keep Ready API only if it provides better enrichment than E-Plus.


### Future RAG Direction

The product catalog is a strong future knowledge base because it contains 102,834 products and large coverage for scientific names, manufacturers, categories, origins, and notes.

Future architecture:

```text
ab_product
  -> ab_product_seo
  -> approved SEO content
  -> embedding pipeline
  -> pgvector
  -> pharmacy AI assistant
```

Only approved public content should be embedded for customer-facing RAG. Separate retrieval-safe fields from non-public medical/internal fields.

