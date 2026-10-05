# Product classification implementation plan

## Inspected architecture

The native `website_sale.product_public_category_action` owns `/odoo/ecommerce-categories`. Its list and form have no custom inherited views in the inspected `ecom19` database. Classification rules and product synchronization belong to `ab_website_sale_product/models/ab_product.py`. The product card supplies ingredient, concentration, medicine flag, manufacturer, groups, scientific groups, usage cause and usage manner. `is_medicine` defaults to true, so it is insufficient evidence alone.

`integration_queue_job` is installed; `queue_job` is not. The queue table was empty. Existing website sync uses a dedicated worker because the shared runner was previously inactive. This feature will declare the installed queue dependency and use its job execution, transaction and stuck-job recovery mechanisms. Runner activation is deployment configuration and will not be performed against live data during coding.

## Implementation

1. Bundle all four historical files byte-for-byte, with checksums and join documentation. Cache a validated code-to-category evidence index. Never import historical categories.
2. Seed closed taxonomy definitions, separate from website category records. An explicit setup action reuses unique exact matches and creates only missing approved nodes. Ambiguous or misplaced matches require an administrator to bind an existing record before setup. Preserve existing category XML IDs and unrelated records.
3. Refactor existing local classification into a pure deterministic service with prioritized combinations, exclusions and pharmaceutical context. Historical conflicts require review. Missing or weak evidence proceeds to local rules and then optional research.
4. Persist runs, immutable processing evidence, permanent review decisions and a research cache. Include linked and unlinked website templates; all-Abdin scope includes inactive records. Snapshot membership incrementally in background with an upper-ID boundary.
5. Enqueue preparation and bounded processing checkpoints (default 250). Use queue transactions, run/catalog locks and product savepoints. Pause/stop take effect at checkpoint boundaries. Resume pending rows; keep failed evidence when retrying in a new run.
6. Add a scoped OWL client action at `/odoo/ecommerce-product-classification`, native result/review views, and an inherited category-list header button. Poll through authenticated ORM calls; no public custom controller.
7. Persist one primary taxonomy node per product and protect it from synchronization. Manual decisions take precedence. Unknown fallback produces no category and preserves existing categories.
8. Add Arabic translations and automated deterministic, ORM, security, lifecycle and UI integration checks. Use an isolated database, never upgrade or classify the live catalog.

## Deployment configuration

Taxonomy bindings must be resolved before a run starts. Web research uses a provider interface and an optional Brave Search implementation with administrator-configured trusted domains, bounded timeouts and a persistent cache. Missing configuration produces review outcomes. Queue runner configuration must be verified on deployment. Tests and actual verification results are recorded separately after implementation.
