---
name: ab-product-seo-workflow
description: Design, implement or review ab_product_seo bilingual drafts, approval, native-field publishing, versioning, queues and rollback.
---

Read [architecture and ownership](references/architecture.md). The source describes
a planned architecture: inspect the checkout before assuming it is implemented.
`ab_product_seo` was absent from the inspected ecommerce checkout.

1. Preserve `ab_website_sale_product` ownership of template/name/code/price/cost
   sync, flags, descriptions, publication state, categories/tags, images and stock
   snapshots. Do not duplicate sync or assume SEO owns product `is_published`.
2. SEO owns bilingual drafts, generation/review/approval, publishing decisions,
   versions, rollback, audit/publish logs and enrichment tracking. Define a handoff
   for overlapping description fields so sync cannot overwrite approved content.
3. Keep lifecycle vocabulary: draft -> generated -> under_review -> approved ->
   published, with rejected/archived outcomes. Define authorized transitions;
   rejection/archive are not mandatory success stages. Never auto-publish medical claims.
4. Publish approved language-specific native `website_meta_title`,
   `website_meta_description`, `website_meta_keywords`, `website_meta_og_img`,
   `seo_name` and agreed `description_ecommerce` values. Reuse Odoo rendering,
   canonical URLs, OpenGraph/Twitter, hreflang, sitemap and structured data.
5. Version inputs/outputs per product/language. Log approvals and publish
   before/after values, actor and timestamp. Rollback restores an approved version
   through an audited publish event. Make retries idempotent.
6. Reuse installed `queue_job`/`integration_queue_job`: Snapshot -> Generate ->
   Review -> Publish. Historical starting points: 100 products/job and identity
   `seo_product_<product_id>_<lang>`; assess version-aware deduplication.
7. Ready stays optional. Future customer-facing embeddings use only approved
   public content, separate from internal/medical/private fields. Add AI/RAG or
   pgvector only when requested.

Read [Phase 0 baseline](references/phase-0.md) as historical measurements, not
current counts. Architecture-only requests mean no code/files/commits; the old
architecture prompt does not block an explicit implementation request.
For the original architecture brief and its complete deliverable checklist, read
[architecture request](references/architecture-request.md) only when planning SEO.
