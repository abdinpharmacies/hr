# Historical website category evidence

Source: `/home/abdin_02/Mohamed_tips/work/website_ecommerce/categories`.
All four source files were inspected recursively and copied without alteration.
`manifest.json` records their byte sizes and SHA256 hashes. No source files were excluded.

These historical categories are evidence, **not the target taxonomy**. The classifier never imports these CSVs as live category or product records. The approved taxonomy has eight roots and at most one child level; it is defined in `services/classification.py` and seeded as definitions by `data/classification_taxonomy.xml`.

| File | Purpose and relevant fields |
| --- | --- |
| `notes.md` | Original explanation of the dataset joins; retained verbatim. |
| `ecommerce_products.csv` | 24,216 variant rows. `template_id` identifies the historical template; `template_default_code` is the E-plus product code. Names and descriptions provide reference context. Variant IDs and historical template IDs are not current Odoo IDs. |
| `ecommerce_categories.csv` | 385 historical categories. `id`, `name`, and `parent_id` reconstruct the tree; `promo_cat` flags promotional evidence. Marketing and brand categories must not become taxonomy nodes. |
| `ecommerce_product_category_rel.csv` | 18,574 relations joining `product_template_id` to `product_public_category_id`. |

Match `ab_product.code` (or `product.template.default_code` for an unlinked website template) to `template_default_code`. Then join historical `template_id` to relation `product_template_id`, and relation `product_public_category_id` to category `id`. Preserve leading zeros; codes are trimmed and case-folded, never converted to integers. A variant repeated for the same historical template is not a second product. A code shared by different historical templates, duplicate relations, or contradictory category paths requires review.

`services/historical.py` contains the explicit historical ID mapping. A mapped ancestor may supply a broad approved root; more specific mapped descendants take precedence. Promotional paths are excluded before any mapping. Compatible ancestor/child evidence collapses to the child; incompatible paths require review even when local rules would otherwise match. Missing or unsuitable historical evidence can proceed to local rules and optional web research. The process caches the parsed index once per worker lifetime; restart workers after replacing the evidence bundle or mapping code.
