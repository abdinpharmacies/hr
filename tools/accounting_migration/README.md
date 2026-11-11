# Custom-model migration into a prepared Odoo 19 target

Run with the Odoo 19 virtual environment. Both database names are explicit:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/migrate19/tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_PREPARED_TARGET_DB
```

All four arguments are required. Usage/options print before connecting; `--help`
never connects. There are no automatic-confirmation, database-creation, or module
installation options. The target must already contain its Odoo 19 modules,
standard business records, metadata, and security configuration.

**Source access stays read-only.** Normal source clients may remain connected and
continue writing. The tool never changes source availability or sessions. ID
inspection and extraction share a read-only repeatable-read snapshot; later source
changes are outside the migration. There is no incremental synchronization.

## Selection and identity

- Select shared persistent custom models beginning with `ab`, including `abdin*`.
  Model metadata determines physical tables; a prefix alone never permits deletion.
  Skip transient/abstract models and SQL views. Report omitted source models and
  preserve target-only models. Existing selected custom data is replaced.
- Preserve source custom IDs and custom-to-custom references. Standard records are
  not imported; credentials and group memberships are not copied.
- Require source user/partner IDs >= 7 to exist in the target, including inactive
  records. Extra target IDs are allowed; IDs below 7 are skipped by this check.
  Retain all IDs in reference metadata: unresolved populated references still fail
  preflight, including references to low IDs. Equal user/partner IDs are accepted
  without comparing names, logins, or emails.
- Resolve other standard IDs through XML IDs, structural identities, reviewed
  unique keys, or explicit mappings. Equal numeric IDs and group display names
  are not identity evidence.
- Import only shared stored fields, honoring explicit renames/conversions.
  Skip source-only and nonstored target fields and report reasons in preflight.
  Raw extraction files remain unchanged. Incompatible shared fields, required
  values, and unresolved shared references still stop preflight. Do not invent
  placeholders, weaken required constraints, or recalculate stock/prices.

## Table checkpoints and availability

1. Ask approval for identity validation and commit its metadata checkpoint.
2. Extract the source snapshot while the target is online. Ask approval for the
   complete table-processing window; create and verify a full online target backup.
3. Block new target connections and terminate other target sessions. Stage the
   retained extraction, run preflight, capture incoming references and original
   foreign-key definitions, and commit setup with relevant FKs removed.
4. Replace each physical custom table in its own transaction: DELETE + adapted
   INSERT SELECT + ID/count validation + XML-ID repair + sequence adjustment +
   success checkpoint. **A failed table rolls back to its previous rows, and later
   tables continue. Earlier successful table commits remain durable.**
5. Process incoming-reference remapping, external-field updates, attachment import,
   attachment fields, and relation tables through separate table transactions.
   Skip relations requiring a failed custom table and report them. Preserve
   prepared standard/target-only associations. Attachment scope uses successfully
   copied models and their eligible links; failed owners are excluded.
6. Validate successfully imported values/links. Attempt every removed FK in an
   independent transaction. Keep successful constraints; leave failed constraints
   absent and report them for manual repair. Run read-only fresh-registry and
   representative branch checks for successfully copied models.
7. Save the result and reopen the target, **including runs with failed tables or
   missing constraints**. The reopened target may contain mixed old/imported data.

There is one approval for the table-processing window, not one prompt per table.
Enter, no, or EOF cancels before that window. The target stays offline across all
individual commits and FK restoration attempts. PostgreSQL and other databases
are never stopped. Controlled interruption attempts constraint restoration before
reopening. The watchdog restores target access after controller failure, including
SIGKILL; it does not repair data or restore constraints. Server outages can prevent
immediate reopening; inspect `availability.json` and `watchdog.log`.

NOT NULL, unique, and check constraints remain enforced. Temporary FK removal
covers references into selected custom/relation tables and FKs on those tables,
preventing cascading deletion while supporting cycles and self-references.
Incoming references are mapped through reviewed identities only for successfully
replaced models; references to failed models retain their original IDs.

## Failure reports and accepted exceptions

Private run directories are under `/opt/odoo19/migration-runs/`. The command prints
the exact path. Reports are updated during processing:

- `failed_tables.json`: table, failed/skipped operation, safe error type and
  SQLSTATE/constraint metadata. A failed later operation does not undo the table's
  earlier committed copy.
- `failed_foreign_keys.json`: table, constraint, local/referenced columns and
  table, original definition, executable `restore_sql`, safe failure reason, and
  accepted-exception status. No PostgreSQL row-detail/business values are logged.
- `table-setup.json`: original constraints and private capture-table descriptions,
  retained for manual inspection after an interruption.
- `verification.json`: terminal status, successful models, committed operations,
  failures, and attachment/omission information. Database checkpoint records are
  authoritative if a report cannot be written.

Terminal output gives counts and report paths. Status/exit behavior:

| Status | Meaning | Exit code |
| --- | --- | --- |
| `complete` | All operations validated; no missing FKs | 0 |
| `finished_with_exceptions` | Only explicitly accepted FK failures remain | 0 |
| `finished_with_errors` | Failed/skipped operations, validation/report errors, or unaccepted FK failures | 2 |

To silence individual warnings for reviewed constraints, configure exact names and
reasons before starting a new run:

```json
"accepted_foreign_key_failures": [
  {"table": "ab_example", "constraint": "ab_example_parent_id_fkey", "reason": "Reviewed legacy exception"}
]
```

The tool always attempts restoration. Accepted failures remain in the saved
report and summary counts. It never infers that a missing constraint is harmless.
Exception rules are tracked with mapping revisions. Resume validates completed
work before adopting corrections; accepted FK exceptions never hide saved failures.

## Mappings, XML IDs, and attachments

`mappings.json` contains reviewed field/selection conversions, XML-ID aliases,
integer links, polymorphic references, and source-model aliases.
`ab_accounting_tracking.je_line` is copied as its original integer audit reference,
including historical IDs whose journal lines no longer exist. It is not an
`integer_links` relationship. The separate computed `je_line_id` is not imported.
This correction can reuse the saved extraction after the reported preflight
failure; rerun normally without `--reset`.

`prepared_rules.json` retains format 1 and supports:

- `stable_keys`: reviewed non-null unique identity columns, initially currency
  `name`, country `code`, and language `code`. Ambiguity blocks; groups, users,
  partners, and attachments cannot use these overrides.
- `external_ids`: model -> source ID -> reviewed existing standard target ID.
- `incoming_ids`: custom model -> old target ID -> replacement source custom ID.
- `ignore_fields`: model -> field -> explicit exclusion reason.
- `branch_manager_xmlids`: model-name glob -> reviewed manager/regional-manager
  group XML IDs bypassing the representative branch audit. System administrators
  bypass first. This does not modify permissions or memberships.
- `accepted_foreign_key_failures`: exact reviewed exceptions described above.

For example, `"incoming_ids": {"ab_example": {"7": 13}}` maps old target custom
record 7 to copied source record 13. It does not relocate source IDs.

For successfully copied custom models, match source XML IDs by `(module, name)`,
verify their model, and repair their destination to the source custom ID. Exclude
`__export__`; do not parse numbers from XML-ID names or copy `ir_model_data.id`.
Preserve unrelated aliases and target `noupdate`; new aliases use `noupdate=true`.
A failed copy rolls back that model's XML-ID changes with its data.

Attachments are limited to copied owners and eligible stored-field/M2M links.
Allocate collision-free target attachment IDs and resolve standard references.
Both configs must specify `data_dir`; filestores are
`data_dir/filestore/DB_NAME`, and resolved roots must not overlap. Read source files
only. Copy verified files atomically, fsync, reuse identical files, and reject
conflicting content. Missing source files retain database records/metadata and
appear in `attachments.json`. Inline binary and URL records are retained. File
publication can survive a database rollback; existing conflicting files are never
overwritten. Activity import is skipped with the extraction count retained;
chatter messages and followers are not imported.

## Retry, compatibility, and reset

The table workflow uses **run format 2**. Existing format-1 runs are rejected before
live changes. Review their state before preparing a separate attempt.

**Rerun the same command without `--reset` to resume.** Successful table copies
are skipped, including tables that succeeded after an earlier table failed. For
example, if tables 1, 2, and 4 committed and table 3 failed, the next attempt copies
only table 3. A failed external update or relationship operation retries that
operation without recopying the successfully imported table.

Retry uses the **original saved extraction**, staging, reference captures, and
attachment IDs. It does not re-extract source changes or create a new backup.
Missing/corrupted extraction or changed database identities stop processing.
Before the first extraction completes, retry can refresh its incomplete snapshot;
source identity changes require revalidation.

You may correct mappings and compatible model definitions for failed work. The
script replans it using the saved source data. Completed data, XML IDs, field
shapes, relationship mappings, and recorded table fingerprints are checked before
adopting a mapping revision. A correction that would alter committed work is
rejected with the affected table/operation; successful tables are not automatically
overwritten. Physical table identities cannot change within an existing run.

Existing format-2 runs gain resume metadata without a reset. If such a run has
committed copies but no saved mapping baseline, first retry with its original
mapping files to establish that baseline; then apply failed-table corrections.
If those original files cannot be established, the script reports insufficient
compatibility evidence instead of guessing. Format-1 runs remain incompatible.

Dependent operations track the models they covered. Newly successful models
unblock pending references and relations. Dynamic references use retained original
values; already remapped IDs are not remapped again. Newly eligible attachments
are added using the existing ID map, without duplicating previous imports.
Matching FKs already restored manually are accepted. Removed or failing FKs retain
restoration SQL in the report.

Each attempt retains database history and an `attempt-N.json` summary. Current
failure reports contain outstanding failures; successful retries remove resolved
failures. A fully successful repeat run revalidates the data and skips all copy
operations. Overall processing approval remains; there are no per-table prompts.
There is no automatic business-data repair or undo of earlier commits. The backup
is the original online snapshot, not a rollback of all committed work.

Optional `--reset` asks `Reset migration state? [y/N]`, then removes only the
selected target's private `prepared_migration_work`, `prepared_migration_source`,
and `prepared_custom_migration` schemas and matching run directories, including
backups/logs/extraction. It preserves public records and installed modules and exits.
Rerun without `--reset` afterward. It refuses committed table setup/imports,
completed runs, active migrations, offline targets, changed identities, or unsafe
paths. Pre-import partial directory cleanup can be retried. Source access and
availability are never changed.

## Progress and validation

Progress emits stage labels and five-second updates. Staging COPY distinguishes
server rows from file bytes. INSERT SELECT and validation use phase heartbeats;
rows become durable only after their table checkpoint commits. Logging and
monitoring use a separate read-only connection to `postgres`; business values and
SQL parameters are not logged. Approval prompts pause periodic console output.

Observe an active run without restarting it:

```bash
/opt/odoo19/venv19/bin/python tools/accounting_migration/watch_progress.py \
  --target-config /opt/odoo19/config/migrate19.conf \
  --stage /opt/odoo19/migration-runs/YOUR_RUN_DIRECTORY
```

Use `--once` for a single observation. An absent backend does not imply success;
inspect the result and failure reports. Other diagnostics include
`id-validation.json`, `preflight.json`, `snapshot.json`, `failure.json`,
`orm-validation.log`, `progress.json`, `progress.jsonl`, and `migration.log`.
Treat all run files/backups as confidential.

The retired initializer remains isolated in disabled `legacy_migrate.py`. The
historical atomic importer is retained for regression fixtures; the public entry
point uses the independent table workflow. See `VALIDATION.md` for test coverage
and remaining production rehearsal limitations.
