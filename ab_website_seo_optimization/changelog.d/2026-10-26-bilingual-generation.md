# Bilingual SEO generation

## Current changes before commit:

- Give AI generators explicit English/Arabic copy instructions for every field and section, preserving brand names, codes, quantities and units without inventing claims or padding descriptions for ranking.
- Request review-only localized product names from the selected assistant or configured pipeline generators, including Arabic suggestions, instead of limiting English suggestions to a selected Groq assistant.
- Reject untranslated product identities and wrong-script content during generation, approval and native-field publication. Keep Latin brands, technical units and URL slugs valid in Arabic content.
- Preserve existing product records, SEO drafts and published content. A bounded read of local SEO record 12 confirmed one active SEO record with two deterministic language rows, not duplicate SEO records for that product.
- Allow natural Arabic word order and supported definite articles/conjunctions/prepositions without weakening fact or medical-claim checks.
- For Arabic only, remove instructions to copy the safe template verbatim; retry repetitive Arabic model descriptions once, then retain fact-valid wording as a review-required draft with an explicit repetition warning.
- For Arabic only, deduplicate keyword variants that differ only by package suffix and allow one useful phrase when facts are sparse. Preserve the previous English prompt, retry instructions, keyword generation and validation behavior.
- Treat identical Arabic about-product, meta and short descriptions as review warnings, request one rewrite, and retain fact-valid drafts if repetition remains. Keep the corresponding English duplicate-copy checks blocking.
- Preserve the earlier validated Arabic draft if its optional rewrite returns malformed JSON; reject malformed responses when no valid candidate exists. Keep actual validation failures blocking and prevent errors from an earlier attempt being attached to a later malformed response. Preserve these review warnings through pipeline validation.
- Add the validation message to both Arabic catalogs and update regression fixtures to provide an actual Arabic identity for bilingual generation.

Files changed:
- `models/enrichment_pipeline.py`
- `models/enrichment_provider.py`
- `models/product_seo_translation.py`
- `models/product_seo_version.py`
- `models/seo_template_workflow.py`
- `services/seo_templates.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_seo_templates.py`
- `changelog.d/2026-10-26-bilingual-generation.md`

## Validation

- Follow-up `duplicate_copy:about_product` fix: 61 executed tests passed, zero failures/errors on the isolated database. Covered Arabic duplicate warnings, provider retry and draft retention, unchanged English duplicate rejection, and unsupported claims remaining blocked. Log: `/tmp/seo-duplicate-validation.log`. The running Odoo process started at 10:29 on 2026-10-27, after the preceding repetition fix but before this follow-up; this follow-up still requires process reload. No new UI labels or translation entries were needed.

- 2026-10-27 repetition fix: 57 executed tests passed with zero failures/errors on isolated `codex_seo_selector_20261027`. Added regression coverage for repeated valid Arabic, malformed optional rewrites, stale error isolation, unsupported claims, and warning persistence through pipeline validation. Log: `/tmp/seo-repetition-final2-validation.log`. No new UI labels were introduced by this fix; existing Arabic catalog entries remain unchanged. The running application has not been restarted or upgraded.

- Isolated database: `codex_seo_languages_20261026`, cloned from inactive `codex_seo_assistant_20261006`; no live database writes or service restarts.
- The first upgrade exposed outdated storefront dependency tables in the historical clone. Targeted upgrades of `ab_website_sale_product`, `ab_ecommerce_storefront` and this module brought only the isolated database up to date.
- Final targeted SEO upgrade and regression run: 52 executed tests, zero failures/errors. Suite: `TestSeoTemplates`, `TestSeoLanguages`, and the existing Groq English-name translation test. An additional regression confirms the previous English prompt and keyword behavior. The Arabic retry test first returns copied template wording, then verifies acceptance of natural fact-grounded Arabic and distinct keyword phrases. External model replies were mocked; live model wording quality was not evaluated.
- Both Arabic catalogs passed `msgfmt --check-format`, following an Odoo POT export. Runtime checks confirmed different English/Arabic approval errors and the Pending Review action translation.
- Python syntax and `git diff --check` passed. The isolated clone has no copied filestore, producing missing historical attachment warnings; the focused tests passed.
- Deterministic mode does not invoke an AI model. AI Wording uses the updated instructions; missing translations in deterministic mode require review instead of being accepted as localized copy.

## Recent relevant commit

- Commit: `b4567f07f57e8a766805831395ef67dbd6a44c98`
- Author: Mohamed Fawzy
- Date: 2026-10-13
- Original subject: `ab_website_seo_optimization/DOCS: record SEO generation changes and validation`
- Documented generation feedback, product-button feedback and pending-review navigation.

Files changed:
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`
- `changelog.d/2026-10-06-template-generation-feedback.md`
- `changelog.d/2026-10-11-product-button-feedback.md`
- `changelog.d/2026-10-12-pending-review-menu.md`
