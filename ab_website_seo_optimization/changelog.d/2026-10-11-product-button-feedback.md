# Product optimization button feedback

Recent relevant commit: `69e7201` Mohamed Fawzy 2026-09-29 `ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow`.

Current changes before commit:
- Reopen the SEO form after a single product optimization request so the queued state is visible immediately; refresh the form to see the completed or failed result.
- Reopen the same form after confirming a replacement of complete SEO fields.
- Retry malformed AI JSON once and allow a fresh request after a cached formatting failure.
- Build internal keywords from distinct trusted facts so the deterministic draft passes its keyword rule.
- Include the grounded product form and package in the Personal Care About the Product section, including an idempotent update for existing templates.
- Write package-based deterministic summaries, include the package in the General About the Product section, and update existing General templates.
- Label product code, package, form, brand and manufacturer facts in English and Arabic Product Information sections.
- Guide Groq with the available product facts, reject generic or unsupported claims and repeated words, and retry invalid output with specific validation feedback.
- Keep a selected AI assistant exclusive for generation; use pipeline generator fallback only when no assistant is selected.
- Retry Groq after temporary quota or network failures instead of reusing a cached failure.
- Cover both button paths, queued feedback, and malformed response recovery in tests.

Files changed: `models/product_seo.py`, `models/product_seo_optimize_confirm_wizard.py`, `models/enrichment_pipeline.py`, `models/enrichment_provider.py`, `models/seo_template_workflow.py`, `services/seo_templates.py`, `data/seo_templates.xml`, `data/seo_template_general_about_upgrade.xml`, `data/seo_template_personal_about_upgrade.xml`, `i18n/ar.po`, `i18n/ar_001.po`, `README_SEO_TEMPLATES.md`, `__manifest__.py`, `tests/test_product_seo.py`, `tests/test_seo_queue.py`, `tests/test_enrichment.py`, `tests/test_seo_templates.py`, `changelog.d/2026-10-11-product-button-feedback.md`.

Validation: 78 targeted tests passed on `codex_seo_assistant_20261006`; both Arabic catalogs passed `msgfmt --check`. The SEO module was upgraded on `ecom19` and its Python workers reloaded after the last code change. Groq job 46 recovered after a temporary quota wait and generated accepted English and Arabic review drafts for product 555. Deterministic job 45 updated the draft for product 78234 through its review proposal. Neither draft was published.

Further changes for product 72249:
- Extract the literal 10 CM*10 CM dimension as a specification and add a General Specifications section, with Arabic title translation.
- Make descriptions, About content, keywords and SEO name distinct from the package-only catalog name where trusted facts allow it.
- Put empty medical detail fields on an optional tab; do not fabricate ingredients, warnings, contraindications or storage.
- Reject repeated phrases and catalog codes in descriptive copy. Clean repeated dimension and code clauses, and replace unsupported AI keywords with trusted product phrases.
- Give Groq a grounded reference only after an invalid first reply, repair at most two invalid descriptive fields, record the repair, and allow a fresh request after a cached template-validation failure.

Validation: 126 module tests passed on `codex_seo_assistant_20261006`; both Arabic catalogs passed `msgfmt --check-format`. The SEO module was upgraded on `ecom19`. Product 72249 remains in review and is not published. Its exact English catalog name is missing, so English SEO wording still uses the Arabic product term.

Further source enrichment changes:
- Add an explicit supplier description field on the product SEO form; feed it into grounded generation without treating catalog operational notes as supplier copy.
- Read visible package text through Groq vision when a real product image is present, cache by image checksum, and mark the extracted text for review.
- Apply the two source facts to the About the Product template while keeping source-free optional sections empty.
- Keep Groq image reading out of deterministic runs and preserve the selected assistant for text generation.

Validation: 129 targeted module tests passed on `codex_seo_assistant_20261006`; both Arabic catalogs passed `msgfmt --check-format`. The real-image path was tested with a mocked Groq response because this database has placeholder product images. The module was upgraded on `ecom19`, workers were reloaded, and port 4092 returned HTTP 200. Runtime field labels were verified as Supplier Description and وصف المورد. Live Groq draft run 60 for product 72249 reached the provider quota and is waiting for automatic retry; it was not published.

Final English-name follow-up:
- Ask Groq to translate only the Arabic product term into a short English noun phrase when the English catalog name contains Arabic, preserving size and package text.
- Ground English drafts in that suggested name, keep the Arabic source name for Arabic, and require review of the unverified translation.

Validation: 131 module tests passed on `codex_seo_assistant_20261006`. Live run 60 later retried successfully and produced both review drafts without publishing; its English draft still showed the Arabic catalog term, motivating this follow-up.

Final Groq verification:
- Use Groq GPT-OSS low reasoning effort for short name translation; the default effort returned empty visible text within the small response budget.
- Require a recognized translation of شاش as gauze and فازلين as Vaseline before an English name suggestion can enter a review draft. Normalize the two-word product term to natural English order.
- Normalize About the Product citations from the English name suggestion to the underlying catalog name and keep the suggestion out of Arabic prompts.

Validation: 131 targeted tests passed again, both Arabic catalogs passed `msgfmt --check-format`, and port 4092 returned HTTP 200 after the live upgrade and worker reload. Live run 64 derived `10 CM*10 CM Vaseline Gauze 1 BOX`, but Groq generated unsupported wording in the English draft and then exhausted its current quota. The run is waiting until `2026-10-12 00:00:00` UTC for retry. The prior review draft remains available; nothing was published.

Quota status follow-up:
- Replace the raw `quota_exhausted` and `all_generators_unavailable` status codes on the product SEO form with a clear message that no new draft is ready and the queued run will retry automatically.
- Verify the configured 200,000 daily token limit and 199,367 tokens used for the selected Groq assistant. The free-plan GPT-OSS 20B limit is also 200,000 tokens per day, so the local limit was preserved.

Validation: 132 targeted tests passed on `codex_seo_assistant_20261006`, both Arabic catalogs passed `msgfmt --check-format`, and the live form status was checked in `ar_001` after upgrading `ecom19` and reloading workers. Run 64 remains queued for `2026-10-12 00:00:00` UTC; no new draft was published.
