# Odoo 15 → Odoo 19 accounting migration with resume

Run with the Odoo 19 virtual environment. You choose both databases:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/migrate19/tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_NEW_TARGET_DB
```

These four arguments are required. There are no migration subcommands, date filters,
filestore arguments, or reusable-stage arguments. `--help` prints usage.

A new target starts a new migration. Repeat the same command with the **same target**
to resume an owned run. The script discovers its stage directory, verifies the
source/target identity and database ownership token, and holds a per-target lock.
Saved model plans and seed-move rows are compared in Python's canonical model-name
order, independently of PostgreSQL locale collation. This allows a committed
mapping checkpoint to resume without weakening row-content validation.

Unowned or ambiguous existing targets are refused. No database is dropped or
recreated. Close other target connections before running; the script does not
terminate sessions or disable connections. The target must remain dedicated to
migration until runtime verification passes; external writes invalidate this
exclusive-use recovery contract.

For the existing failure, use `--target-db migrate_test3`. The first resume verifies
the legacy staging schemas, counts, indexes and extraction checksums before
adopting its 158 committed COPY tables. The rolled-back mapping must run once more.
Both account and allowed-field authorization `group_id` fields are now optional. An isolated targeted
`ab_accounting` upgrade removes the old target NOT NULL constraint when needed;
no arbitrary group is assigned to unassigned source rows. Upgrade detection and
post-upgrade checks cover both tables.

For the later `migrate_test4` failure on the 261 unassigned allowed-field
authorizations, rerun with `--target-db migrate_test4`. Its 158 COPY checkpoints
are already committed; resume upgrades the accounting addon, reuses those tables,
and reruns early validation before mapping. `allowed_field_id` remains required.

For the `migrate_test5` numeric configuration reference failure, repeat the original
command with `--target-db migrate_test5` after applying the seed adapter fix.
The Odoo 19 `base.template_portal_user_id` parameter is mapped as a `res.users`
reference. Reviewed base/mail size, cooldown, retention and Boolean settings stay
unchanged even when their numbers match relocated IDs. Unknown numeric settings
still stop the migration, now naming the parameter keys without exposing values.
The seed adapter version is part of checkpoint compatibility; the failed mapping
had not committed, so its existing COPY checkpoints can be reused.

The subsequent serialized-metadata blocker is handled by structural inspection of
view XML and email-template HTML. Reviewed field help/module descriptions are
excluded; domains, contexts, QWeb expressions and record URLs are checked separately
from styling and literal prose. Numeric UI flags and download flags are not record
IDs. Unknown JSON metadata retains conservative checks. Suspected references are
not rewritten automatically: `seed-reference-blockers.json` identifies the record,
XML IDs, language, expression location and candidate IDs for review. Malformed view
XML also blocks. Adapter version 4 requires compatible mapping checkpoints.

Action domains resolve IDs against the action model and declared field relations,
so an `ir.cron` ID is not mistaken for a relocated account/currency ID. Literal
many2one `default_<field>` action-context values follow their related model's seed
moves through temporary and final IDs. Other defaults stay unchanged. Unsupported
affected expressions remain blocked; no context expression is executed. Planned
context snapshots are fingerprinted with seed references and guarded at update time,
so a changed context aborts the transaction rather than being overwritten.
For `migrate_test5`, the Salaries action's account default moves from 22 to 267;
document type 7 and cost center 629 retain their source IDs.

Bulk manifest version 3 records an explicit `column_order` array for each table.
Both COPY directions use this array; alphabetically sorted JSON metadata does not
change the transfer order. All column lists are validated before staging starts.
Older manifests are rejected instead of guessing their original COPY order.

## Strict source-ID contract

Every copied business/master record keeps its source numeric ID. This includes
users, partners, companies, accounting, inventory, attachments, E-Plus, and custom
business groups such as `ab_accounting_auth_group`. There is no source-ID offset
or collision renumbering. One model-level identity rule replaces per-record maps.

Technical lookup records (security `res.groups`, model/field definitions, views,
actions, menus) retain their installed Odoo 19 identities. They are matched by
reviewed XML IDs; user membership points to the matched target groups. Their
numeric IDs can differ, while the users' IDs remain unchanged.

Initialized target business/master records are matched by XML identity and approved
unique native keys. Matching seeds move to the corresponding source IDs; unrelated
seeds occupying needed IDs move above both source and target maxima. Two steps via
a disjoint temporary range handle swaps. Source IDs never change, and seed records
are not deleted. Protected superuser ID 1 must match the source superuser.

Seed relocation and business import commit together. The reference inventory covers
public single-column NO ACTION/CASCADE foreign keys, stored ORM relations, M2M
links, typed polymorphic/reference fields, XML-ID references, company-dependent
JSON, relational defaults, reviewed configuration links, and hierarchy paths.
Unsupported foreign keys, unknown populated integer references and potentially
embedded IDs in serialized metadata stop with `seed-reference-blockers.json`.
Arbitrary application code/free text cannot be safely interpreted as an ID map;
new reference conventions require reviewed adapters, not guessed replacements.

`seed-relocations.json` records target-only moves. The committed strict plan stores
seed hashes, reference metadata and format version 3; changed seed state or adapter
contracts are rejected on resume. Before business loading, old format-1/2 mapping
metadata is archived transactionally and replaced by a strict plan. COPY checkpoints
are retained. **A previously committed old-policy business/runtime checkpoint is
rejected**, including by the already-completed shortcut. Use a new target or a
separately reviewed recovery for that case.

Source XML IDs for copied records are restored using preserved business IDs, while
existing Odoo 19 technical XML IDs are not replaced. Existing target `noupdate`
flags stay unchanged. Newly restored source-only business aliases use
`noupdate=true`; original flags remain in the export and working XML-ID table.
Conflicting XML-ID ownership/record identities block commit. The numeric IDs of
`ir_model_data` rows themselves are technical and are not preserved.

The current process is not hot-updated. Run the revised script manually after the
old process has stopped. Runtime checks and seeded-reference coverage have not yet
been validated against a real migration by the code-update workflow.

## Recovery boundaries

| Phase | On retry |
| --- | --- |
| Module initialization / languages | Verify completed setup; retry missing setup. |
| Extraction | Reuse a complete snapshot. Archive incomplete files and restart all extraction under one new source snapshot. |
| Raw COPY | Skip each committed table after metadata/index checks. A partially copied table rolls back and is copied again. |
| Strict ID/seed plan | Reuse a compatible format-3 plan. Archive older mapping metadata and replan without repeating COPY. |
| Business load | Convert, insert, link, and verify all final tables in one transaction. Repeat this phase if it rolls back. |
| Registry/view/permission checks | Retry these alone when business data already committed. |
| Completed migration | Report strict-policy completion without reimporting; reject old-policy committed results. |

Checkpoints commit in the same transaction as the data they describe. Manifest and
phase fingerprints reject incompatible reuse. Mapping fingerprints include target
registry metadata, mapping rules, and seed-adapter contracts; compatibility version constants must be bumped
when mapping/business semantics change incompatibly. Logging/diagnostic-only fixes
need no version bump. Raw staging stays unchanged: normalized XML metadata, source
defect flags, filtered relationships, and converted data use working tables.

For new checkpoints, row counts and checksums were verified before commit; normal
resume avoids rehashing/recounting completed tables. Legacy adoption performs those
checks once. Missing/corrupt files for an unfinished COPY table stop recovery; they
are never silently replaced with rows from a newer source snapshot. Legacy adoption
is bounded to complete staging followed by schema-adaptation failure with no
committed mappings. Other pre-checkpoint failure shapes require an explicit adapter.

Previous failure reports are retained under `attempts/`; logs append an attempt
marker. `preflight-errors.json` aggregates directly detectable required/selection
issues before mapping, and `validation-errors.json` aggregates model validation
errors before business loading. Resume does not promise that unsupported source
values will pass without an adapter.

## What the command does

1. Lock the target name and either create a fresh target or resume a verified owned run.
2. Discover the selected source's installed accounting dependents and physical
   schema using a read-only, repeatable-read PostgreSQL connection.
3. Discover source languages from `res_partner.lang`, including delegated user
   preferences. Initialize a fresh Odoo 19 database with current addons and
   compatibility support, with database connections enabled.
   Activate `en_US`, `ar_001`, and any other source contact/user languages, then
   load installed module translations. Verify language setup before extraction
   starts; source user/contact preferences are preserved.
4. Extract all historical rows in the accounting scope, all persistent E-Plus
   models, and supported prerequisite tables. There is no six-month cutoff.
   Framework lookups are extracted for mapping, not restored over Odoo 19.
   Attachment extraction is scoped to included models and known model aliases.
5. Load protected raw staging tables with PostgreSQL `COPY`. Generate explicit
   column lists, preserve business IDs and resolve technical references, convert supported schema changes, and apply business
   rows with set-based `INSERT ... SELECT` statements. There are no per-record
   ORM create calls for the historical bulk load and no SQLite data staging.
6. Resolve relationships, translations, company properties, audit references,
   user roles, and default-company membership. Unsupported populated differences
   stop the run with a report rather than silently losing values.
7. Copy available attachment files using `data_dir` in the source configuration
   and Odoo's target filestore path. The source configuration must explicitly
   specify `data_dir` to avoid guessing which operating-system user's filestore
   contains the files.
8. Verify mapped counts and values, constraints, password hash compatibility,
   and user-company consistency. Rebuild target-only derived fields and parent
   paths. Reload the registry in a second isolated worker, compile relevant views,
   and exercise representative explicit branch-role profiles.
9. Report verification results and print a command for the isolated local
   development server. Scheduled jobs stay disabled. Database connections remain
   enabled throughout the run, including after failures and interruptions; the
   script does not terminate other database sessions. A visible, connectable
   database may still contain only initialization or staging data after a failure.

The Odoo server is discovered beside this checkout (`../server`). Source Odoo 15
Python modules are inspected as text; no Odoo 15 registry is loaded by Python 3.12.

## Progress and reports

Every run creates a new private directory under `/opt/odoo19/migration-runs`.
Its location is printed immediately. Console output is also written to
`migration.log`; worker output is streamed live and saved separately.

A background reporter emits status every five seconds, including the phase,
model/table, operation, elapsed time, processed rows, and affected rows. A separate
read-only database connection samples the worker backend's state, query duration,
wait event, blocking PIDs, and COPY row/byte counters. Monitor queries have a
one-second timeout; unavailable monitoring does not stop the migration. Module
installation before a worker cursor exists has elapsed-time heartbeats only.

Identity allocation, converted-row preparation, and business insertion use
500,000-row indexed keyset batches. Rows are reported after each SQL batch returns;
COPY also exposes live PostgreSQL counters. Long validation/index queries report
activity and waits, not invented row counts. Business batch rows remain **pending commit**;
there are no per-batch business commits. Each verified staging COPY table commits separately. Commit and rollback have separate events.
Per-operation ETA appears only after three batches and fifteen seconds of work;
there is no overall migration ETA.

Console and file output use independent bounded queues and daemon writers. A
separate pipe-reader thread drains worker output. Slow output cannot hold up SQL;
periodic messages coalesce, overflow drops older messages with a notice, and
shutdown waits are bounded. Logs are best effort during output failure or abrupt
termination. PostgreSQL checkpoints, not these logs, determine safe recovery.
An already-running worker keeps its old logging; the changes apply to new runs.

Example (illustrative counts):

```text
[MAPPING] | model=abdin_eplus.r_sales_trans_h | operation=allocate IDs | status=pending commit | processed=500,000/29,463,325 | affected=500,000 | elapsed=35s
```

Use the same four command-line arguments; no logging flags are required.

Important files:

- `progress.jsonl`: structured progress and diagnostic events.
- `progress.json`: atomically replaced latest operation status.
- `migration.log`, `init-target.log`, `bulk-import.log`, `bulk-smoke.log`: readable logs.
- `bulk-manifest.json`: current source snapshot, table metadata, counts, checksums.
- `tables/*.copy`: raw text COPY files, including original omitted-column values.
- `schema-comparison.json`: source and destination physical column metadata.
- `languages.json`: required/activated languages, translation-loading completion,
  and safe failure diagnostics. Language setup must complete before COPY.
- `verification.json`: results, omitted columns, excluded out-of-scope roles,
  missing files, unresolved reference counts, and runtime checks.
- `bulk-error.json`: safe error details, processing phase, table, and code locations
  for loader failures; database row values remain redacted.
- `failure.json`: an incomplete-run marker when the orchestrator stops.

The raw staging schema is retained in the destination for traceability. This
uses additional disk space; the extraction files and staging tables are not an
incremental synchronization mechanism.

## Development defect policy

The previously approved development policy is built into this workflow:

- Missing source attachment contents are flagged; original path, checksum and
  size are preserved. No replacement contents are invented.
- Known missing inventory origins and journal-line audit references retain their
  original provenance and quantities, with compatibility guards against edits.
- Approved obsolete E-Plus columns may be omitted without adding dummy fields.
  All omissions are listed, and original values remain in protected extraction.
- Groups belonging entirely to applications outside the migration scope are
  reported and excluded. Unknown roles for included applications stop the run.
- Retired report fields are omitted only from the specifically reviewed saved
  report-column relationships.

This is a development migration, not a production cutover. It never reports
`cutover_ready=true`. A PostgreSQL snapshot keeps database rows consistent but
cannot freeze external filestore writes; changed attachment checksums stop the run.
The isolated development server and migration worker block outgoing integrations.
Those process-local controls do not isolate a separate Odoo server you launch.
The normal database manager can list these databases subject to its usual
ownership and filter settings; visibility does not mean verification succeeded.

The code update does not reopen previously failed databases. If you want to
restore connections to the earlier targets manually, run these as their owner
or a PostgreSQL administrator:

```sql
ALTER DATABASE migrate_test1 ALLOW_CONNECTIONS true;
ALTER DATABASE migrate_test2 ALLOW_CONNECTIONS true;
```

These commands only enable connections. They do not resume or finish migration.

## Verification status of the implementation

See `VALIDATION.md`. Code-level checks do not establish that a particular source
has migrated successfully. The full migration and its runtime checks execute only
when you run the command. Legacy ORM helpers and their tests remain available as
internal reference code; the public command does not use their old subcommands.

## Reviewed orphan quarantine

A private `quarantine-policy.json` in the owned run directory can authorize exact
source IDs for orphan E-Plus purchase details and orphan attachments. It is bound
to the immutable extraction fingerprint; newly discovered or changed references
still fail. This policy does not change committed ID mapping checkpoints and is
included in business-checkpoint compatibility.

Complete original rows and missing-parent IDs are retained in
`accounting_migration_quarantine.records`, with PUBLIC schema/table access revoked
and no Odoo model exposing these records. Filtered working views exclude only the
approved rows from business loading, reference resolution, XML-ID restoration and
normal attachment file handling. Original staging tables and COPY exports remain
untouched. Existing valid parents, count differences, changed payloads or active
business copies of quarantined IDs fail verification.

`quarantine-report.json` lists the reviewed IDs and file outcomes. Available blobs
are copied into the private run's `quarantine-filestore`; files absent from the
source are explicitly recorded as `missing_in_source`, never reported as copied.
The database quarantine commits together with business data; before that, report
`committed` is false. Verification reconciles active rows plus quarantined rows
against the original snapshot. A passing run with quarantine remains development
only and does not imply a complete production cutover.
