# Odoo 15 to Odoo 19 migration tools

## CSV-controlled replication

Use this explicit mode to check selected standard/custom table counts and copy
tables with different counts, or explicitly force replacement, using source IDs
and shared physical columns.
Stored M2O/M2M references to ignored tables use
shared XML IDs, as described below. It does not invoke the legacy ORM/identity
workflow documented later in this file.

First export a new review file (existing CSV/sidecar paths are never overwritten):

```bash
/opt/odoo19/venv19/bin/python tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_TARGET_DB \
  --export-table-plan /private/path/table_plan.csv
```

Export reads both catalogs without database writes or downtime and creates
`table_plan.csv.metadata.json` alongside the UTF-8 CSV, both mode 0600. Keep this
sidecar with the CSV. Rows represent distinct persistent registered model tables
in either database, not transient models, views, or unregistered tables. Literal
model `_table` overrides are discovered from configured installed addon paths
without executing addon code or starting a registry.

The exact CSV header is:

```text
table_name,model_type,existance,available_target_selections_json,source_missing_columns_list,target_missing_columns_list,replicate,replicate_override,column_default_value_json,source_fk_columns_json,target_fk_cloumns_json
```

`table_name` is a physical public table. `model_type` defaults to `custom` for
`ab*` model ownership, otherwise `odoo` (including mixed ownership). `existance`
is `source_only`, `target_only`, or `both`, based on physical catalog presence,
independent of whether a table contains records. Selecting a model table without
usable `id` on both sides is not supported. Import automatically excludes
source-only and target-only model tables, even when their replication flag is 1;
you do not need to remove those rows manually. Eligibility comes from the bound
physical catalog metadata, not the editable diagnostic `existance` cell.

`available_target_selections_json` replaces both former first-value sample
columns. Export no longer reads any business sample rows or places large stored
payloads inside CSV cells. It shows only physical selection columns present in
target but absent from source, for example:

```json
{"available_target_selections": {"target_field_name": ["bottom", "sided"]}}
```

Choices are technical keys from `ir_model_fields_selection`, joined to
`ir_model_fields` by `field_id`, ordered by `sequence, id`, without labels.
Repeated keys/shared model ownership are deduplicated. No registry is started.
A field with no stored choices shows `null` (dynamic/unresolved), never guessed
values; no matching fields yields `{"available_target_selections": {}}`.
These diagnostics do not add selection validation or mapping to replication.
To choose a value, enter `{"target_field_name": "bottom"}` in
`column_default_value_json`.

Export and import require CSV metadata version 3 and the exact new header.
Older CSV versions and `replicate_source_id` headers are rejected: export a new
CSV and sidecar. There is no old-column alias or legacy CSV conversion. The
diagnostic-refresh helper accepts only the new format and preserves both flags.
Current
checkpoints use run format 4 and row-count verification policy `csv_count_v1`;
XML-ID artifacts carry their own versioned policy. Missing-column arrays mean
source-minus-target and target-minus-source respectively. FK JSON uses the
supplied paired catalog query, including composite keys.

Edit only the operational cells:

- `replicate`: `1` selects normal count-based replication; `0` or blank ignores
  the table unless override is 1. Defaults are custom=1 and Odoo=0. Missing CSV
  rows are ignored. There is no standard-table allowlist. Copied tables retain their
  source IDs; references to ignored tables follow the XML-ID rules below.
- `replicate_override`: `1` selects the table and forces transactional DELETE/COPY,
  even with `replicate=0`, matching counts, or a successful old checkpoint.
  Defaults to 0; blank also means 0. Force remains active on every rerun until
  you set it back to 0. This does not bypass both-side existence, usable IDs,
  schema/database binding, constants, backup, or SQL/FK validation.
- `column_default_value_json`: `{}` by default, or a JSON object such as
  `{"company_id": 1, "active": true, "note": null}`. Constants name target
  physical columns and override shared source values for every imported row.
  These are target values and bypass relationship mapping for that column.
  An `id` override is rejected. Diagnostic cells do not control execution.

| replicate | replicate_override | Action |
|---|---|---|
| 0/blank | 0/blank | Ignore |
| 1 | 0/blank | Copy only when counts differ |
| 0/blank | 1 | Force delete and recopy |
| 1 | 1 | Force delete and recopy |

For example, set `replicate_override=1` for `res_partner` when counts match but
source partner ID 6 is missing from the target. The copy restores the source ID
set instead of treating equal counts as completion.

Then apply the reviewed file:

```bash
/opt/odoo19/venv19/bin/python tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_TARGET_DB \
  --table-plan /private/path/table_plan.csv
```

Only selected tables present on both sides are eligible; these need usable IDs. Schema/database
binding is checked before backup, then target schema/FKs are checked again after
exclusive access. The actual extraction uses a fresh read-only repeatable-read
snapshot; exported catalogs/choices do not freeze the imported data.

CSV mode retains private COPY files but creates **no PostgreSQL staging tables**.
CSV mode proceeds automatically through backup, exclusive target access,
replication, FK restoration, and reopening the target. There is no
`Continue? [y/N]` confirmation for this workflow.

Verification uses **row counts only** (`csv_count_v1`): the source count is read
from the retained extraction manifest and the target uses `SELECT count(*)`.
For ordinary model tables, equal counts mean `verified_existing` with no
DELETE/COPY unless `replicate_override=1`, regardless of previous checkpoint
owner. Different counts or an override cause the transactional copy. IDs,
values, constants, and mapped-reference differences are not compared when counts
match. No full-row hashing, PostgreSQL composite normalization, or verification
SQLite indexes are created. A target COUNT still reads database pages.

Eligible M2M tables are **always fully replaced on every run**, including when
counts match or selected endpoint models were skipped. DELETE and streaming COPY
run in one transaction, rebuilding the complete table from mapped source links.
There are no additive imports or per-link target-existence INSERT checks.
Replacement removes valid target-only memberships as well as obsolete links.
After copying, the target count must equal the number of emitted links, with
raw source rows accounted for as inserted + missing-mapping skips + duplicates.
Native SQL constraints remain enforced. Source COPY file checksums and XML-ID
artifact integrity are separate from count verification.

Shared columns copy by identical physical name. Target-only nullable columns
without constants receive explicit NULL; target-only NOT NULL columns need a
constant when rows are imported. No SQL/Odoo/Python default fallback, field
renames, selection/type adapters, translations, company-property construction,
or XML-ID repair run. PostgreSQL parses/enforces its native target types; a
value it cannot accept rolls back that table. Generated columns are omitted and
cannot be overridden. Source-only columns are skipped.

Stored M2O columns shared by source and target use source IDs when their
referenced table is selected. Otherwise, map each non-NULL source ID through an
exact shared `ir_model_data` `(module, name)`, checking the expected model and the
actual target record. NULL stays NULL. Missing matches roll back that table,
including nullable M2O fields; independent tables continue. No numeric-ID or
record-name fallback is used, and no referenced records are created. Plain
integer, polymorphic, and nonstored fields are not mapped. Missing endpoint
model/table metadata is rejected rather than copying an unverified reference.

M2M associations follow automatically when either endpoint table is selected,
provided the relation table and both endpoint tables exist in both databases.
One-sided model/relation tables and relations with one-sided endpoints are
excluded before strict binding checks, reported with reasons as warnings, and
never created or copied. For example, a source-only
`ab_hr_job_ab_visit_report_report_rel` is skipped even when `ab_hr_job` is selected.
If both sides exist but columns, declarations, or endpoint roles differ, planning
still fails rather than guessing. The same rules apply to fresh catalog discovery
and operation planning from retained extraction metadata.
Both selected means source IDs at both endpoints. One selected means retaining
that endpoint's source ID and mapping the other endpoint through shared XML IDs.
Neither selected means no relation operation. Full replacement applies in both
selected cases; existing target links absent from mapped source data are removed.
Physical relation table and endpoint-column roles identify an association, so
Python field renames such as `groups_id` to `group_ids` are accepted without
guessing renamed columns. Missing XML-ID matches skip links with warnings, even
when that leaves an empty relation. Ambiguous aliases or SQL errors roll back
that table's DELETE/COPY. Selected endpoint operations must succeed first.

Mapped endpoint pairs are deduplicated with a private, disk-backed ID index,
keeping memory bounded. If duplicate mapped pairs carry different extra-column
values, the operation fails rather than choosing a payload. The temporary index
is removed after success/failure; it is not a source/target content verifier and
creates no PostgreSQL staging table. Copy progress reports source rows processed.
`m2m_replacement_report.json` records source/inserted/skipped/deduplicated counts,
timings, and `m2m_replace_v1` policy; operation status is `m2m_replaced`.

Old additive operation checkpoints cannot skip rebuilding relations. Existing
compatible source extractions and XML-ID snapshots are reused without changing
their artifact policy or triggering a fresh extraction just for this change.
CSV headers and ordinary model override behavior remain unchanged.

After the table/relation operations and before FK restoration, the existing
scoped orphan cleanup removes surviving links whose endpoint ID has no target
record, using SQL `NOT EXISTS` checks. It does not scan unrelated/excluded M2M
tables, ordinary M2O tables, or registered model tables. Failed/unfinished selected
endpoints block cleanup. Valid surviving links and all endpoint/business records
are preserved by cleanup; replacement itself intentionally removes extra target
memberships. Server-cursor candidate discovery and bounded DELETE batches recheck
absence, identify rows across partitions, and commit deletion checkpoints/audits
atomically. Private JSONL files contain only deleted endpoint IDs. Active incoming
CASCADE/SET NULL/SET DEFAULT FKs block cleanup instead of cascading into records.

Before live work, the verified full target backup and existing downtime watchdog
are used. Incoming/outgoing FKs touching tables that need writes (including FKs owned by
ignored tables) are saved and temporarily dropped, preventing CASCADE/SET NULL
changes to ignored rows. Unrelated constraints stay untouched. Failed removals
block affected operations. Restoration is attempted independently and missing
constraints remain reported with repair SQL; no data is repaired automatically.

Each successful table commits its count, verification policy, transactional owned-ID
sequence restart, and marker together. For ascending unit-increment sequences,
the next value is `max(id)+1` or the declared start for an empty table. Unsupported
sequence layouts fail the table instead of guessing. Native PK/NOT NULL/unique
and check constraints remain enforced. For adopted matching tables, advance a
sequence only if it is behind the imported IDs; never rewind it.

Runs live under `/opt/odoo19/migration-runs/csv_<plan_id>/`, with authoritative
checkpoints in private schema `csv_replication` (run format 4, separate from
legacy format 2). Rerun the same command to compare source/target counts again.
Changing constants or XML-ID mappings does not force a recopy when counts match.
Use `replicate_override=1` when replacement is required despite equal counts.
Forced copies are reported as `forced_copy`, with copy reason `replicate_override`;
ordinary count-triggered copies remain `copied`. Forced endpoints also replay
their M2M operations and run the normal orphan cleanup/FK restoration.

A different plan/run is accepted for the bound target. The previous checkpoint
is archived under `archive:<uuid>` in the checkpoint table, with its constraints
and operation records intact. Outstanding FK restoration definitions carry into
the active run. Malformed recovery information blocks takeover, and offline
targets require an unambiguous recovery marker for the same database identity.
Original run directories and artifacts are not deleted. Adoption is based on
current counts, not old success markers. Old content-verification artifacts are
not loaded or required when resuming with count-only verification.
Source XML-ID aliases and relationship metadata are captured in that same
read-only snapshot. Private, indexed SQLite files retain source aliases,
prepared-target lookup decisions, and each operation's decisions/issues, with
policy and SHA-256 checks. Target matches are resolved after exclusive access,
before any selected table is copied. Each attempt resolves current target XML
IDs for operations that need copying. Skipped operations do not revalidate each
row or reference. If
`ir_model_data` itself is selected, retain the original prepared-target map for
retries in that run too, because the metadata namespaces have been replaced.
Actual reference mapping checks target records while preparing target lookup metadata.

Existing version-3 CSV/sidecar files remain usable; older CSVs require a fresh
export, while their checkpoints/run artifacts remain intact. An incompatible/incomplete extraction,
including one predating XML-ID metadata, automatically starts a fresh
`generation_<uuid>/` extraction with source rows and aliases in one snapshot.
Adding selected tables or references not retained in the old extraction also
starts a new generation. `active-extraction.json` identifies the active directory;
old snapshots are kept intact and never enriched with newer metadata.
Compatible ordinary resumes reuse the retained source snapshot. Fresh generations
archive the old checkpoint and recheck target counts before skipping.
`--reset` does not manage CSV runs. An all-zero plan, or a plan selecting only
one-sided tables, causes no backup, downtime, or database writes; exclusions are
still reported as warnings.

Reports: `migration_report.md`, `csv-result.json`, `failed_tables.json`,
`failed_foreign_keys.json`, `mapping_report.json`, `verification_report.json`,
`excluded_tables.json`, `m2m_cleanup_report.json`, `m2m_replacement_report.json`, and `attempt-N.json`, plus normal progress/availability
files. They contain counts, operation timings/errors, FK outcomes, and optional
action results. Mapping reports include resolved-reference/skipped-link counts,
issue categories, and private per-operation SQLite artifact paths with detailed
source IDs and affected columns. Verification reports include expected/actual
row counts, count-comparison reasons, verification timings, and outcomes:
`verified_existing`, `copied`, `forced_copy`, `m2m_replaced`, or `failed`.
Exclusion reports identify skipped model/M2M tables, absent source/target tables,
and missing endpoint tables. They cause `complete_with_warnings`, not failed
operations. Operation counts include only the current eligible operations,
while historical checkpoints and outstanding FK restoration remain preserved.
Cleanup reports give deleted link counts, endpoint bindings, private deleted-ID
file paths, final relation row counts, skipped relations, and failures. Successful
removals cause `complete_with_warnings`; cleanup failures cause
`finished_with_errors` and still allow independent FK restoration attempts.
There are **no user/partner identity checks or
reports**, broad missing-reference/orphan scans, or ORM smoke tests in CSV mode. FK/SQL
failures still surface normally. Exit status remains 0 for complete/warnings,
2 for genuine operation failures. COPY files/backups can contain private business
and credential data when their tables are selected; never publish run artifacts.

### Optional file action

Without extra actions, `ir_attachment=0` means no metadata/file copy and
`ir_model_data=0` means no XML-ID repair. At `1`, each is simply fully replaced
using source IDs when replacement is needed. No attachment-ID allocation/remapping occurs.

Append `--extra-actions menu` for the no-action/copy-filestore menu, or use
`--extra-actions copy-filestore` directly. File copying requires
`ir_attachment=1`. The selected action is saved for retries. Roots are:

```text
source-config data_dir / filestore / source-db
target-config data_dir / filestore / target-db
```

The action copies the current source directory tree after attachment rows commit,
preserves target-only files, reuses identical files, and refuses conflicting
content or symlink traversal. Files publish atomically; failures can retry
without recopying successful tables. It is a directory merge at action time,
not a transactional filestore snapshot. Disabled file actions require neither
`data_dir` nor filesystem access. Extra actions are named internal functions,
not arbitrary SQL/Python evaluation.

## Existing prepared-custom workflow

The remaining sections describe the existing command **without CSV flags**.

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

### Fingerprint performance

Each operation computes identical table/column/filter fingerprints once, without
changing their format or ordering. This temporary reuse ends with the operation;
resume still independently verifies committed data before continuing.

In the public raw-reference workflow, XML-ID repair and external-field or
attachment-link steps with no corresponding scalar fields retain an existing
full custom-table fingerprint. Their actions, relation writes, security guards,
and atomic success markers still run. Missing or narrower checks fall back to a
fresh fingerprint. Actual custom-table changes always refresh their checks.
No CLI flags, checkpoint conversion, or reset are needed for existing format-2
runs. See `VALIDATION.md` for disposable benchmark results and reproduction.

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
