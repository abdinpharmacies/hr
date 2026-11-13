# Prepared custom-model migration changes

## Current changes before commit:

- Add read-only registered-table CSV/sidecar export and reviewed-plan execution, with explicit table replacement controls, source IDs, constant overrides, and no identity/ORM audit behavior in CSV mode.
- Copy retained source files directly into targets without PostgreSQL staging; preserve NULL/default rules, M2M replacement/additive operations, atomic checkpoints, sequence restarts, and resume.
- Save/remove/restore incoming and outgoing FKs touching selected tables, preserving ignored rows; recapture constraints after exclusive access to avoid online schema races.
- Retain backup/gating/watchdog recovery and add an opt-in resumable filestore action; document commands, limits, tests, and the measured disposable direct-copy benchmark.
- Replace large sample columns in new CSV exports with database-only target selection choices and `existance` status; preserve legacy plans, conversion controls/binding, and committed resume compatibility.
- Map stored M2O/M2M references to ignored tables generically through shared XML IDs; retain selected endpoint source IDs and explicit target constants, and match renamed M2M fields by physical endpoint roles.
- Fail missing M2O matches and conflicting aliases; skip unmatched M2M links with warnings, block relations after failed endpoint copies, and retain mapping reports with private indexed snapshot/decision artifacts.
- Freeze prepared-target mappings before copying metadata; older/incomplete extractions get a fresh generation without overwriting original artifacts.
- Use retained source counts and target COUNT(*) for CSV verification across run IDs; skip equal-count models/replacement relations without row hashing, type normalization, or verification SQLite indexes, and recopy count mismatches. Replay relations after copied endpoints and check post-write counts.
- Archive prior format-3/4 checkpoints on ownership transfer, retain outstanding FK recovery, and report verified/copied/additive/failed outcomes with comparison evidence; adopted tables never rewind sequences.
- Remove the CSV backup/replication confirmation prompt; continue automatically through backup, downtime, copying, FK restoration, and reopening.
- Restrict model and automatic M2M imports to tables and endpoints present on both sides; exclude one-sided candidates before strict binding validation, retain genuine mismatch errors, and report skip warnings without counting historical/excluded operations.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `csv_actions.py`
- `csv_copy.py`
- `csv_plan.py`
- `csv_relations.py`
- `csv_replicator.py`
- `csv_verify.py`
- `migrate.py`
- `tests/benchmark_csv.py`
- `tests/test_csv_postgres.py`
- `tests/test_csv_replication.py`
- `tests/test_csv_verify.py`
- `tests/test_csv_xmlids.py`
- `tests/test_migration.py`

## a0526994c — emadco88 — 2026-11-12

Original commit subject: `tools/accounting_migration/prepared.py UPD report_only=False for users and partners`

- Make the existing non-CSV identity checkpoint reject missing source user/partner IDs >= 7 instead of saving report-only approval.

Files changed:
- `prepared.py`

## cb1bf68e7 — emadco88 — 2026-11-12

Original commit subject: `tools/accounting_migration/ UPD speed process`

- Deduplicate identical table fingerprints within each operation and retain full checks for raw-policy XML-ID/empty scalar phases, preserving actions, relation writes, and atomic markers.
- Keep digest format, resume verification, format-2 compatibility, protections, and historical strict-policy behavior; refresh after actual custom-table changes or absent full checks.
- Add scope/recovery regressions and a reproducible disposable baseline benchmark; document measured performance without changing application databases.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `table_checkpoints.py`
- `table_resume.py`
- `tests/benchmark_fingerprints.py`
- `tests/test_raw_relationships.py`
- `tests/test_resume_fingerprints.py`

## a31a650ee — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ FIX dead lock`

- Release validation-worker transactions and record caches before import; verify idle/no-lock state before gating the target, and read a fresh snapshot after import.
- Bound custom FK DDL lock waits to five seconds and report affected operations instead of waiting indefinitely.
- Protect standard business rows, native relation tables, aliases, and definitions from migration writes/ALTER; retain scoped attachment/XML-ID data operations only.
- Report protected incoming dependencies and safely skip affected custom replacements, including CASCADE, SET NULL, and composite constraints; continue independent tables.
- Preserve resume fingerprints and clearly label private user/partner ID staging; add real PostgreSQL worker-lock and protected-record/definition regressions.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `prepared.py`
- `prepared_metadata.py`
- `prepared_progress.py`
- `standard_protection.py`
- `table_checkpoints.py`
- `table_resume.py`
- `worker.py`
- `tests/test_prepared_postgres.py`
- `tests/test_raw_relationships.py`
- `tests/test_standard_protection.py`

## 5df1dcb2e — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ FIX missing integer mapping`

- Apply a global raw-reference/report-only policy to the public migration CLI; preserve custom source IDs and standard target records without reference remapping.
- Convert current and future integer/polymorphic declarations into audit-only hints; report missing relationships and identity IDs >= 7 instead of blocking copies.
- Remove relevant FKs before live writes and report restoration failures as nonblocking warnings, including required and composite FKs; isolate genuine SQL failures per operation.
- Preserve prepared incoming references/shared associations and isolate XML-ID conflicts from committed custom copies.
- Retain collision-free attachment allocation and imported-link mapping; preserve source company/reference IDs in company-property JSON.
- Persist policy-aware resume, complete relationship detail/audit reports, constraint definitions/repair SQL, and warning status/exit behavior.
- Add disposable PostgreSQL coverage and update the runbook/validation evidence without migrating an application database.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `mappings.json`
- `prepared.py`
- `prepared_snapshot.py`
- `raw_importer.py`
- `relationship_policy.py`
- `table_checkpoints.py`
- `table_resume.py`
- `tests/test_prepared.py`
- `tests/test_prepared_postgres.py`
- `tests/test_raw_relationships.py`

## 2deddac7f — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ UPD commit staging too`

- Commit each staging COPY, required index, validation, and success marker independently; continue other staging tables after an individual failure.
- Reuse verified staging checkpoints after interruptions or preflight failures; reject changed staging or extraction and adopt retained format-2 staging without recopying it.
- Preserve initial identity checks separately and require every staging table to be ready before preflight or live-table copying.
- Add staging progress/report/history and clarify when staging versus live records are committed.
- Allow confirmed reset of recognized staging-only state while retaining ownership checks and refusal after live setup/imports.
- Add disposable PostgreSQL and controller regression coverage; update the runbook and validation evidence.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `prepared.py`
- `prepared_checkpoints.py`
- `prepared_importer.py`
- `prepared_snapshot.py`
- `prepared_staging.py`
- `reset_migration.py`
- `tests/test_prepared_postgres.py`
- `tests/test_prepared_staging.py`

## a973d4bd3 — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ FIX remove je_line mapping rule`

- Resume failed and interrupted table operations on the same command; skip committed copies and retry failed/dependent work using the original extraction.
- Replan corrected mappings/model fields for failed work while guarding committed data, XML IDs, table identities, and relationships.
- Reuse original incoming-reference captures and attachment ID maps; track model coverage to prevent double remapping and duplicate attachments.
- Adopt existing format-2 checkpoints without a reset, record per-attempt history, and refresh outstanding failure reports after successful retries.
- Retain the existing processing approval and offline target window; revalidate completed runs without recopying their tables.
- Add disposable PostgreSQL/offline resume coverage and update the runbook and validation evidence.
- Remove the accounting tracking `je_line` integer-link override; preserve historical integer IDs even when their journal lines are absent, with a disposable PostgreSQL regression check.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `migrate.py`
- `mappings.json`
- `prepared.py`
- `prepared_importer.py`
- `table_checkpoints.py`
- `table_resume.py`
- `tests/test_prepared.py`
- `tests/test_prepared_postgres.py`
- `tests/test_table_checkpoints.py`

## dc7bca670 — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ UPD commit each table`

- Commit each successful live custom-table replacement and its checkpoint independently; roll back a failed table and continue with later tables.
- Persist original FK definitions and incoming references before removing constraints; restore FKs independently and report unapplied constraints with manual restoration SQL.
- Process incoming references, external fields, attachment links, and relation tables through separate table transactions; preserve failed-model records and skip dependent relations/attachment owners.
- Keep the target offline throughout table processing and reopen with reports, including runs with errors. Support exact reviewed FK exceptions without hiding saved failures.
- Add terminal statuses/CLI exit codes and versioned run markers; reject partial-run automatic continuation/reset while retaining pre-import retry and saved final-result retrieval.
- Add disposable PostgreSQL and offline coverage; update the runbook and validation evidence.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `migrate.py`
- `prepared.py`
- `prepared_importer.py`
- `prepared_rules.json`
- `prepared_snapshot.py`
- `table_checkpoints.py`
- `tests/test_prepared_postgres.py`
- `tests/test_table_checkpoints.py`

## eb4484d88 — emadco88 — 2026-11-11

Original commit subject: `tools/accounting_migration/ UPD add --reset option`

- Add optional confirmed `--reset` for private pre-import schemas and matching run directories; exit after cleanup so the next normal run starts fresh.
- Preserve public records and unrelated runs; refuse active migrations, committed imports, identity changes, and unsafe paths. Support retry after partial directory cleanup.
- Print usage/options at startup and a complete reset recovery command on errors.
- Add CLI and disposable PostgreSQL reset coverage; document behavior and validation.

Files changed:
- `README.md`
- `VALIDATION.md`
- `changelog.d`
- `migrate.py`
- `reset_migration.py`
- `tests/test_migration.py`
- `tests/test_prepared_postgres.py`
- `tests/test_reset_migration.py`

## 3343d652c — emadco88 — 2026-11-11

Original commit subject: `tools/ UPD shared columns only + progressbar`

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
