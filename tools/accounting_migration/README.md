# Custom-model migration into a prepared Odoo 19 target

Run with the Odoo 19 virtual environment:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/migrate19/tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_PREPARED_TARGET_DB
```

All four arguments are required. Usage prints before connecting; `--help` never
connects. The target must already contain its Odoo 19 modules, standard records,
metadata, and permissions. No module/database installation is performed.

## Global relationship policy

The public importer uses **`raw_references_report_only_v1`** for every selected
custom model, including future models. There are no per-field blocking reference
rules and no CLI switch to enable strict relationship mapping.

- Preserve source primary keys for shared persistent custom `ab*` models,
  including `abdin*`. Model metadata identifies physical tables; a table prefix
  alone does not authorize replacement. Skip transient/abstract models and views.
- Copy shared stored reference values unchanged, including integers, real
  Many2one values, polymorphic IDs, and model discriminators. Missing references
  are not replaced with NULL, guessed IDs, or placeholders.
- Standard records keep their existing primary keys. Users, partners, companies,
  credentials, memberships, and other prepared standard business records are not
  imported or overwritten. Their table definitions and native M2M tables also
  remain unchanged, including foreign keys. Prepared incoming references remain
  unchanged. Custom model aliases cannot bypass this protection.
- Scoped technical writes are allowed for **imported attachments** and custom
  XML-ID repair in `ir_model_data`. Allocate collision-free attachment IDs and
  map imported attachment fields/M2M links. Neither technical table has its
  definition or foreign keys changed.
- User/partner identity comparisons check source IDs **>= 7**, including inactive
  records. IDs below 7 are excluded from comparisons but remain in reference
  metadata and copied values. Missing checked IDs are reported, not rejected.
- A valid FK proves that a numeric ID exists, not that source/target identities
  agree. This workflow intentionally adopts the operator's raw-ID policy.
- Field renames, non-reference selection/type conversions, translations, and
  company-dependent JSON conversion remain supported. Company keys and referenced
  IDs in company properties retain source IDs; record-specific properties win.
- Source-only and nonstored target fields are skipped and reported. Actual SQL
  errors such as incompatible values, NOT NULL, primary-key, unique, or check
  violations remain operation failures. Other table operations continue.

`integer_links`, `polymorphic`, `stable_keys`, `external_ids`, `incoming_ids`, and
reference XML-ID mapping declarations do not change reference values or block the
public workflow. The shipped former integer/polymorphic declarations are now
`integer_reference_audit_hints` and `reference_audit_hints`. They identify fields
for reporting only. Legacy/future relationship declarations cannot enable
reference enforcement. Passwords are never extracted through stable-key overrides.

All relationship existence checks and FK restoration failures are report-only.
ORM/branch audit failures are also recorded separately from committed imports.

## Source access and extraction

Source access is **read-only**. The script never changes source availability or
sessions. Source clients can continue writing. ID inspection/extraction share one
read-only repeatable-read snapshot; later source changes are not included.

Private COPY files retain selected custom data, eligible relation/attachment rows,
and necessary metadata. No credentials are extracted. The original extraction is
mandatory after staging starts; missing/corrupted files or a changed snapshot stop
processing. There is no incremental source synchronization.

## Staging and live checkpoints

1. Ask for identity-comparison approval and commit its report/checkpoint.
2. Extract while the target is online. Ask approval for the processing window and
   create/verify the full online target backup `before_import.dump` with SHA-256.
3. Block target connections and terminate its other sessions. For each staging
   table, commit COPY + required index + schema/count/content validation + success
   marker together. Roll back individual staging failures and attempt the rest.
4. Require all staging tables to be ready. Build field plans and report relationship
   declarations without enforcing them. Actual conversion-plan failures become
   individual table errors rather than global relationship blockers.
5. Save relevant FKs and remove only constraints owned by selected custom tables
   and eligible custom relation tables. Standard/public tables outside this scope
   keep all definitions unchanged. If protected rows reference a custom table,
   skip its replacement and report the dependency, including CASCADE/SET NULL and
   composite keys. Continue independent operations. FK DDL waits at most five
   seconds for a lock; unavailable locks become reported operation failures.
6. Copy each custom table in its own transaction. Its DELETE, adapted INSERT,
   ID/count verification, sequence adjustment, and success marker commit together.
   A failed table retains its previous rows; earlier commits remain durable.
7. Repair source custom XML-ID destinations in separate operations using raw
   custom IDs. Preserve target `noupdate` and unrelated aliases; report conflicting
   alias models without undoing copied tables. Skip `__export__` aliases.
8. Import attachments/links and relation tables independently. Preserve existing
   associations in shared prepared standard/target-only relation tables.
9. Attempt each removed custom-owned FK restoration in its own transaction. Leave
   failed constraints absent and report their original definitions and repair SQL.
   Previously missing protected standard constraints are reported without ALTER.
10. Audit relationships, M2M/company-property values, incoming references, metadata
    conflicts, and a fresh read-only registry. Save the final reports and reopen
    the target, including runs with missing constraints or technical failures.

The read-only validation worker rolls back metadata reads and clears record
caches before announcing readiness. The controller verifies its backend is idle
with no transaction or relation locks before gating the target. After import,
validation uses a fresh read-only snapshot. This prevents the worker from blocking
the importer while waiting for its completion signal.

`res_users` and `res_partner` staging progress is labelled
`scope=private-ID-staging-only`: these private tables contain identity IDs, not
public business-record copies.

There is one overall processing approval, not one prompt per table. A failed
preflight/attempt cannot undo committed staging. Progress distinguishes COPY
finished/pending commit, staging checkpoint committed, and live-table committed.
PostgreSQL and other databases are never stopped. The availability watchdog can
reopen the target after controller failure; it does not repair data or constraints.

## Resume and compatibility

**Rerun the same command without `--reset`.** Format-2 runs retain their identity;
format-1 runs remain incompatible.

- Verify committed staging schema, count, index, and content fingerprint, then
  skip COPY/index creation. Failed staging tables are retried from the saved files.
  Verification still reads data. Legacy committed setup can adopt verified staging.
- Skip successful live copies and retry failed/unfinished operations. For example,
  if tables 1/2/4 committed and table 3 failed, only table 3 is recopied.
- Reuse the backup and attachment map. Newly eligible attachments are added
  incrementally, without duplicate records or overwriting existing files.
- Record each operation's relationship policy. Prior mapped-policy commits remain
  unchanged and are identified in the report. They are not silently rewritten to
  raw values. Stored data fingerprints still protect completed work.
- Missing or altered committed staging/live data, changed database/table identity,
  or corrupt extraction stop processing. These are integrity/ownership failures,
  not relationship validation rules.
- Retain attempt history in database checkpoints and `attempt-N.json`. Current
  reports show outstanding findings; later attempts refresh them.

## Final reports and exit status

The command prints its private run directory under `/opt/odoo19/migration-runs/`.
Treat all reports/backups as confidential. Reports include:

- **`migration_report.md`**: human-readable operations, identity counts, warnings,
  technical failures, and pointers to complete detail files.
- **`relationship_report.json`**: machine-readable result, policy, counts, operation
  results, and all captured constraint definitions/outcomes.
- **`relationship_issues.jsonl`**: every recorded finding with table/field/model,
  affected record/reference identifiers, and kind; no artificial row limit.
- **`failed_foreign_keys.json`**: unapplied FKs, safe error metadata, complete
  definitions, executable restoration SQL, and nonblocking warning classification.
- **`failed_tables.json`**: actual SQL/technical operation failures eligible for retry.
- `staging.json`, `id-validation.json`, `preflight.json`, `verification.json`, and
  `table-setup.json`: checkpoint, conversion, source-binding, and integrity evidence.

Audit queries run behind savepoints so invalid reference formats or unsupported
audit queries cannot abort committed copying. Reports omit business payloads,
credentials, SQL parameters, and PostgreSQL row-detail strings. Relationship details
are persisted privately by attempt and exported using streaming reads.

| Status | Meaning | Exit |
| --- | --- | --- |
| `complete` | Operations completed without findings | 0 |
| `complete_with_warnings` | Relationship/FK/ORM findings; copies remain committed | 0 |
| `finished_with_errors` | Genuine table-operation, report, or infrastructure errors | 2 |

Actual removed FKs that fail restoration remain reported even when they involve
user/partner IDs below 7. Low-ID exclusions apply to identity comparisons only.

## Attachments and other limits

Both configs must specify `data_dir`. Filestores are
`data_dir/filestore/DB_NAME`; resolved source/target roots must not overlap. Read
source files only; verify and publish target files atomically with fsync. Reuse
identical files and reject conflicting content. Missing source files retain
metadata and appear in `attachments.json`. Existing target attachments/files are
not overwritten. File publication can survive a database rollback and is reused
on retry. Inline binary and URL attachments are retained.

Activities are reported as skipped; chatter messages/followers are not imported.
Prices and inventory quantities are not recalculated. Full production-scale and
all-branch acceptance remains an operator rehearsal task; see `VALIDATION.md`.

## Reset and observation

Optional `--reset` asks confirmation and removes eligible private migration schemas
and matching run directories, including backups/logs/extraction. It preserves
public records, exits after cleanup, and never changes source access. Recognized
staging-only runs can reset. Live setup/imports, unknown ownership/state, active
migrations, offline targets, changed identities, and unsafe paths are refused.

Observe an active run without restarting it:

```bash
/opt/odoo19/venv19/bin/python tools/accounting_migration/watch_progress.py \
  --target-config /opt/odoo19/config/migrate19.conf \
  --stage /opt/odoo19/migration-runs/YOUR_RUN_DIRECTORY
```

Use `--once` for one observation. An absent backend does not prove success; read
the result/reports. Logging and statistics use a separate read-only maintenance
connection. Other diagnostics include `availability.json`, `watchdog.log`,
`failure.json`, `orm-validation.log`, `progress.json`, and `migration.log`.

The public CLI uses `RawImporter`; historical strict importer primitives and the
disabled legacy initializer remain only for historical regression fixtures.
