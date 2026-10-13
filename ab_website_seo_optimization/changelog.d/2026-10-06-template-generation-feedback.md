# Template generation alignment and failure feedback

## Recent relevant commit

- Commit: `69e72011cc12874ea2b3f3d65cd7390d9b614bf8`
- Author: Mohamed Fawzy
- Date: 2026-09-29
- Original subject: `ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow`
- Introduced category-aware templates, constrained generation and factual validation.

Files changed: relevant files from that commit:

- `models/enrichment_provider.py`
- `models/enrichment_pipeline.py`
- `models/seo_template_workflow.py`
- `services/seo_templates.py`
- `views/seo_template_views.xml`
- `tests/test_enrichment.py`

## Current changes before commit:

- Align AI instructions with the existing validator: preserve complete product identity, restrict metadata vocabulary, and quote cited facts verbatim in every section. Include a product-specific JSON example with supported sections only.
- Request one correction per configured model after a template validation failure. Keep provider quotas, request accounting, validation and mandatory human review in place.
- Include the prompt in the generation cache key so corrected instructions do not reuse failures from older prompts.
- Preserve validation error codes in negative-cache entries and provider/language details in the work item's validation report. Do not retain raw rejected responses or credentials.
- Show queued, waiting, failed and completed draft feedback on the product SEO form. Hide legacy Not Run feedback for enrichment jobs and preserve legacy behavior otherwise.
- Add seven English/Arabic UI messages in both Arabic catalogs using an Odoo POT export.
- Add four regression tests for correction and caching, persistent unsafe-content rejection, product error visibility, and the shaving category's bilingual grounded example.

Files changed:

- `models/enrichment_provider.py`
- `models/enrichment_pipeline.py`
- `models/seo_template_workflow.py`
- `services/providers.py`
- `services/seo_templates.py`
- `views/seo_template_views.xml`
- `tests/test_enrichment.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `README_SEO_TEMPLATES.md`
- `changelog.d/2026-10-06-template-generation-feedback.md`

## Diagnosis and validation

- Read-only inspection of the reported product confirmed Shaving & Men's Care selected the Personal and Household Care template with no category conflict. The queue runner was executing; generation failed validation and another provider timed out. The old implementation discarded detailed validation errors, so the precise rejected wording from those historical requests cannot be recovered.
- The original prompt allowed natural wording and only required verbatim text in selected sections, while the validator required restricted metadata vocabulary and verbatim content in every section. The change aligns the prompt without weakening those validation rules or changing category configuration.
- Targeted upgrade passed on isolated database `codex_seo_assistant_20261006`; validation uses workers 0, cron 0, HTTP disabled and alternate ports 5069/5072.
- Focused enrichment suite: 43 tests passed, zero failures/errors. The initial full run exposed two test-fixture issues: assertion savepoints rolled back the negative cache, and the historical test database lacked the current shaving category mapping. Both fixtures were corrected without changing live category data.
- Final complete module suite: **109 tests, zero failures/errors**, exit 0. Log: `/tmp/ab_seo_feedback_final.log`.
- Both Arabic catalogs pass `msgfmt --check-format`; runtime regression verifies different English/Arabic generation feedback. Python/XML syntax and whitespace checks pass.
- Provider responses are mocked in these regression tests. A fresh successful response from the user's live Groq account is not claimed. No live database upgrade, service restart, API call or publication was performed for this change.
- Exclude development tests and bytecode from runtime production packages.
