# SEO generation through the existing background queue runner

## Recent relevant commit

- Commit: `69e72011cc12874ea2b3f3d65cd7390d9b614bf8`
- Author: Mohamed Fawzy
- Date: 2026-09-29
- Original subject: `ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow`
- Added persistent enrichment work items, provider cooldowns, resumable discovery and template review gates.
- The queue integration preserves those generation and review rules while replacing cron-driven execution.

Files changed: the full module list is available through `git show --name-only 69e7201 -- ab_website_seo_optimization`. Relevant files:

- `__manifest__.py`
- `models/enrichment_pipeline.py`
- `models/seo_template_workflow.py`
- `views/seo_template_views.xml`
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`

## Current changes before commit:

- Depend on the installed `integration_queue_job` module and register the SEO worker on `root.seo`.
- Queue individual and bulk generation immediately without global cron workers. Process one enrichment product per task, committing progress and continuation together.
- Preserve provider cooldowns through queue ETA, deduplicate pending and running checkpoints, and ignore obsolete callbacks after Resume, Retry, cancellation or archival.
- Recheck manager access, active user and company access during execution; retain the requesting user and narrow the task company context.
- Allow old queued runs to enter the runner through Resume Job. Preserve the legacy cron XML ID with an enqueue-only callback; disable it on fresh installs.
- Hide the obsolete items-per-tick setting and document runner setup, failure recovery and the separate dataset-import cron requirement.
- Add both Arabic catalogs for queue metadata and errors, using references from an Odoo POT export.
- Add 12 queue regression tests. Earlier assistant/mode and form fixes are documented in `2026-10-06-generation-assistant.md`.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/seo_queue.py`
- `models/enrichment_pipeline.py`
- `data/seo_queue.xml`
- `data/seo_bulk_cron.xml`
- `views/seo_template_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_seo_queue.py`
- `README_ENRICHMENT.md`
- `README_SEO_TEMPLATES.md`
- `changelog.d/2026-10-06-seo-queue-runner.md`

## Validation

- Targeted upgrade and complete module suite on isolated database `codex_seo_assistant_20261006`: **105 tests, zero failures/errors**, exit 0. Log: `/tmp/ab_seo_queue_final_tests.log`.
- Queue tests cover automatic single/bulk scheduling, bilingual drafts, continuation, deduplication including started tasks, delayed provider retry, legacy-run recovery, cancellation/archival, transaction rollback, lock contention, protected metadata, manager execution, reader denial, inactive users and cross-company denial.
- Actual HTTP runner smoke test with `max_cron_threads = 0`, workers 0, root capacity 1, test-only database filter and HTTP/gevent ports 5069/5072: two sequential `root.seo` tasks completed, yielding four review-required translations for two test products. Zero provider calls or publication. Only the temporary validation server was stopped afterward.
- Runner log: `/tmp/ab_seo_runner_smoke.log`; setup and verification scripts: `/tmp/ab_seo_runner_setup.py`, `/tmp/ab_seo_runner_verify.py`.
- Both Arabic catalogs pass `msgfmt --check-format`. Runtime field labels differ between `en_US` and the installed Arabic language `ar_001`; the generic `ar` catalog was validated statically because that language code is not active in the test database.
- Reviewed the monitor's discovery code: registered `queue.job.function` definitions and execution records are already supported, so no monitor changes are required. Browser verification remains unavailable.
- The historical database copy lacks attachment files and logs attachment-read notices; these did not fail the tests or queue execution.
- No live database upgrade, service restart or live Groq request was performed. Deployment still requires the targeted module upgrade and loading the updated Python code through the normal service process, followed by Resume Job for existing queued runs.
- Keep development tests and bytecode out of runtime-only production packages.
