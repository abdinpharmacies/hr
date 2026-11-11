# Prepared custom-model migration changes

## Current changes before commit:

- Import shared stored fields across all copied models; report source-only/nonstored fields instead of requiring an adapter for each omitted field.
- Apply the same policy to cached/new M2M metadata and attachment fields; retain raw extraction and scope attachments to copied owners/shared links.
- Add asynchronous five-second progress for backup, staging COPY, indexing, validation, replacement, mapping, attachments, and commits.
- Add a read-only watcher using maintenance statistics while target access is blocked; keep logging/monitoring failures nonfatal.
- Validate field filtering, attachment scope, unchanged payloads, prompt pauses, and progress isolation with disposable fixtures.
- Update the runbook and validation reference.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `common.py`
- `prepared.py`
- `prepared_importer.py`
- `prepared_progress.py`
- `prepared_snapshot.py`
- `tests/test_prepared_odoo.py`
- `tests/test_prepared_postgres.py`
- `tests/test_prepared_progress.py`
- `watch_progress.py`

## a0ad32130 — emadco88 — 2026-11-11

Original commit subject: `tools/ FIX migration code trial 1`

- Introduce prepared-target checkpoints, preserved custom IDs, XML-ID repair, native-reference mapping, attachment importing, and recovery.
- Leave source availability unchanged and validate only source user/partner IDs >= 7 while retaining low-ID reference metadata.
- Isolate the retired initializer and add disposable PostgreSQL/Odoo regression fixtures.

Files changed:
- `README.md`
- `VALIDATION.md`
- `availability.py`
- `bulk_importer.py`
- `changelog.d`
- `legacy_migrate.py`
- `migrate.py`
- `prepared.py`
- `prepared_importer.py`
- `prepared_metadata.py`
- `prepared_rules.json`
- `prepared_snapshot.py`
- `source.py`
- `tests/test_bulk.py`
- `tests/test_languages.py`
- `tests/test_prepared.py`
- `tests/test_prepared_odoo.py`
- `tests/test_prepared_postgres.py`
- `tests/test_resume.py`

## 0687472d3 — emadco88 — 2026-11-11

Original commit subject: `NEW INIT from dev-central19`

- Initialize the prior accounting migration tooling, source extraction, strict-ID adapters, progress reporting, recovery libraries, and regression fixtures.

Files changed:
- `.gitignore`
- `README.md`
- `VALIDATION.md`
- `action_seeds.py`
- `adapters.py`
- `batching.py`
- `bulk.py`
- `bulk_importer.py`
- `common.py`
- `dev_server.py`
- `importer.py`
- `languages.py`
- `mapping.py`
- `mappings.json`
- `migrate.py`
- `preflight.py`
- `progress.py`
- `quarantine.py`
- `resume.py`
- `seed_metadata.py`
- `seeds.py`
- `source.py`
- `tests/check_idle_support.py`
- `tests/integration_rehearsal.py`
- `tests/serve_fixture.py`
- `tests/test_accounting_groups.py`
- `tests/test_action_seeds.py`
- `tests/test_bulk.py`
- `tests/test_languages.py`
- `tests/test_mapping.py`
- `tests/test_migration.py`
- `tests/test_progress.py`
- `tests/test_quarantine.py`
- `tests/test_resume.py`
- `tests/test_resume_postgres.py`
- `tests/test_seed_metadata.py`
- `tests/test_seeds.py`
- `tests/test_strict_odoo.py`
- `worker.py`
