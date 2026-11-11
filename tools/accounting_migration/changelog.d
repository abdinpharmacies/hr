# Prepared custom-model migration changes

## Current changes before commit:

- Replace the public initializer with approved checkpoints for existing prepared targets; isolate the retired controller and disable its CLI.
- Leave source availability and sessions untouched; read a consistent source snapshot while other clients can continue writing. Restore target access after checkpoint success, rollback, or controller failure.
- Check source user/partner IDs >= 7, skip lower IDs only for validation, and allow extra target records. Retain low-ID metadata for audit/reference mapping.
- Preserve custom IDs, repair XML IDs atomically, and validate external mappings and incoming references.
- Resume existing failed-ID runs with fresh read-only inputs, revalidate changed source IDs before extraction, and retain completed snapshots unchanged.
- Import scoped attachment records/files while retaining missing-file records and resumable mappings.
- Add read-only Odoo registry validation, disposable PostgreSQL/Odoo acceptance fixtures, reviewed mapping configuration, and recovery documentation.
- Keep historical regression fixtures separate and use valid SQL composables in their mocked adaptation path.

Files changed:
- `README.md`
- `VALIDATION.md`
- `availability.py`
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
