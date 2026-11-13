# Prepared-target migration validation

## Global installed-module XML-ID repair (2026-11-13)

Full suite: **416 tests, 406 passed and 10 optional tests skipped**, in 217.354
seconds. The final focused XML-ID suite passed all **13 tests** after the preview
preservation adjustment. Compilation and `git diff --check` passed.

The separate identity option now audits aliases owned by every target-installed
module, including persistent models outside `ab%`. Registered-model/table
discovery does not start an Odoo registry. Copy evidence follows the active CSV
checkpoint archive chain and requires matching source/target identities plus a
committed source-ID replacement receipt; row-count skips alone are insufficient.
Existing core user/partner association checks remain available independently.

Thirteen disposable PostgreSQL regressions cover both accounting namespaces,
dangling aliases, aliases pointing to existing wrong records, missing aliases,
non-`ab` models, target-only/generated/uninstalled namespaces, absent/conflicting
copy evidence, legacy format-3 receipts, malformed/cyclic history, missing source
records, table overrides, bounded ID batches, preserved `noupdate`, per-model
rollback, stale previews, independent progress, and idempotent reruns. The focused
suite passed after making proposed `noupdate` values reflect the preserved target
values exactly.

The real Odoo rehearsal creates two temporary installed seed addons in a
generated database, restores a separate source fixture, and simulates source-ID
replacement while leaving target XML IDs stale. A seeded upgrade fails with a
duplicate name, and a base upgrade reproduces the portal-login conflict. Running
only the global XML-ID/configuration action fixes both namespaces and the core
identity mappings; a subsequent real base/seed-addon upgrade succeeds with three
seed records preserved and no duplicate creation. Temporary addons are confined
to the disposable fixture directory and are not shipped as production addons.

Read-only planning against `main19` inspected 80 installed module namespaces:
12,356 eligible source aliases and 15,315 target aliases. It proposed 76 verified
changes across four models, including 62 account-guide aliases covering both
accounting namespaces. Unsupported/ambiguous/missing-source cases were reported
without applying changes. The user's custom-model diagnostic (exactly excluding
`__export__`) found 133 source aliases and 110 target aliases across all modules.
No application repair, backup, upgrade, or availability change was run against
the real source or target during this work.

## Explicit backup consent (2026-11-13)

Final full suite: **403 tests, 393 passed and 10 optional tests skipped**, in
152.227 seconds, including the real disposable Odoo base-upgrade rehearsal.
The prepared-controller test was also rerun after adding its explicit-skip
assertion: **1 passed**. Compilation and `git diff --check` passed.

Imports and repairs now require a per-run backup decision. Offline regressions
verify that blank/invalid input cannot authorize a backup, cancellation takes no
backup, flags are mutually exclusive, noninteractive imports without a flag stop
before dispatch/connections, export does not request consent, and reruns do not
inherit consent. Declining backup bypasses creation, checksum reads, and archive
validation even when an old corrupt backup exists. Created/reused/skipped and
failed outcomes are retained in private per-attempt reports.

Disposable PostgreSQL tests exercise CSV import, prepared-workflow resume, and
database repairs with backup explicitly declined. Repair tests also verify that
requested-backup failures stop before repair writes or target exclusion, and
that interruption recovery rolls back/reopens the target with either backup
choice. Existing tests explicitly authorize their fixture backups. No backup,
import, repair, module upgrade, or availability change was run against `main19`
or the real source database during this change.

## Interactive menu and separate repairs (2026-11-13)

Final suite: **389 tests, 379 passed and 10 optional tests skipped**, in 153.671
seconds with the disposable PostgreSQL tests and real Odoo base-upgrade rehearsal
enabled. `git diff --check` passed. A real terminal invocation displayed options
1/2/3/0; entering `0` exited with status 0. Existing CLI parser/dispatch tests pass,
and the CSV importer/planner/COPY/mapping/verification files are unchanged.

The 22 new tests cover shared atomic 0600 defaults, invalid settings, export
overwrite refusal, export/import/fix dispatch isolation, cancellation, and native
login/FK failures. PostgreSQL scenarios reproduce the five missing constraints
and their orphan counts (9/183 wizard rows, 140 payroll rows, 13 report rows, and
one Discuss membership), restore them independently, preserve unrelated records
and translations, and verify repeat execution has no remaining repair changes.
Additional cases cover composite MATCH FULL/partial NULL references, audit
timeouts, changed prerequisites, ambiguous field aliases, incoming CASCADE
dependencies, rollback without a completion receipt, and interruption recovery.
The complete repair controller was exercised with actual backup creation/archive
validation, before/after reports, transactional receipts, and availability gating.

The Odoo rehearsal initialized a fresh disposable Odoo 19 base database and
restored its backup into a separate disposable source clone. It deliberately
pointed the portal-template alias/configuration at the public user. A real
`-u base` then failed with `res_users_login_key`. Running only the separate core
identity repair allowed the subsequent real `-u base` to complete successfully.
These module upgrades were confined to generated disposable databases, not the
application target or its full addon set.

Reproduce (requires CREATEDB and the local Odoo server):

```bash
MIGRATION_PREPARED_TEST_CONFIG=/opt/odoo19/config/migrate19.conf \
MIGRATION_ODOO_SERVER=/opt/odoo19/server \
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -v
```

The maintenance config is used only to connect to `postgres` and generated
`codex_migration_test_prepared_*` fixture databases. Real `main19` and source
`abdinpharmacies` were inspected read-only to validate repair planning; no
application migration, repair, module upgrade, or availability change was run
against them. The supported current repair preview reports six alias/config
changes, one payment-type insertion, 13 field-reference updates, one reviewed
membership removal, and five FK restorations. Running option 3 remains an
explicit operator action, with audit/selection/confirmation before target writes.

## Authoritative M2M replacement (2026-11-13)

Final suite: **367 tests, 357 passed and 10 optional tests skipped** in 59.297
seconds on an isolated PostgreSQL 16 instance over a private Unix socket. Offline
discovery: **367 tests, 186 passed and 181 skipped**. The CSV subset contains
**130 tests**. Compilation and `git diff --check` passed. No application migration,
manual repair, CSV edit, or source/target availability change was performed;
database mutations used generated disposable fixtures only. The temporary cluster
was stopped and removed after validation.

- All eligible M2M operations now use full transactional DELETE/streaming COPY
  on every run, regardless of matching counts or successful old additive markers.
  Ordinary model count skips and version-3 override controls remain unchanged.
  Target-only memberships are removed; neither-selected/unrelated relations and
  excluded schemas remain untouched. Failed selected endpoints block replacement.
- Reproduce the three direct role conflicts (users 3, 4, and 9409) with different
  source/target group IDs and renamed groups fields. Even with equal relation
  counts and count-skipped users, mapped source replacement removes obsolete
  Internal/Portal/Public memberships and restores missing source memberships.
- Keep selected endpoint source IDs and exact XML-ID mapping of ignored endpoints.
  Missing matches skip links with warnings; zero mapped links and empty sources
  correctly clear target associations. Ambiguities and conflicting extra-column
  values roll back replacement and preserve valid old target links.
- Bounded private endpoint-ID indexes deduplicate mapped aliases and duplicate
  source pairs without loading the relation into memory or creating PostgreSQL
  staging. Identical extra columns survive; conflicting payloads fail. Temporary
  indexes are removed after success/failure/interruption.
- Count accounting covers source rows, inserted links, missing-mapping skips,
  and duplicate links. Post-copy counts validate emitted links, so filtering or
  deduplication does not cause false raw-source-count failures. Progress exposes
  processed source rows; reports use `m2m_replaced` and `m2m_replace_v1`.
- Existing source extraction bytes and XML-ID artifact policy stay unchanged;
  reruns do not require a fresh source extraction for this policy change. Tests
  cover self-relations, repeated/checkpointed runs, transactional interruption,
  rollback/retry, FK recovery, and defensive cleanup of post-replacement defects.

## Version-3 replication controls and forced recopy (2026-11-13)

Final suite: **357 tests, 347 passed and 10 optional tests skipped** in 49.241
seconds on an isolated PostgreSQL 16 instance over a private Unix socket. Offline
discovery: **357 tests, 186 passed and 171 skipped**. The CSV subset contains
**120 tests**. Compilation and `git diff --check` passed. Existing operator CSVs,
sidecars, and application databases were not changed, exported, or migrated.
Database writes were limited to generated disposable test fixtures; the temporary
cluster was stopped and removed after validation.

- New exports contain `replicate` and `replicate_override` with metadata version
  3. Defaults remain custom=1/Odoo=0 for normal replication and override=0 for all
  tables. Old metadata versions and old column-name headers are rejected with a
  re-export instruction, with no alias or legacy conversion branches.
- All blank/0/1 flag combinations are covered. Override alone selects and forces
  a table even with replicate=0; invalid flags/constants still fail and one-sided
  forced selections remain excluded. New-format diagnostic refresh preserves
  both controls, row order, plan identity, and binding, without changing inputs.
- Equal-count override copies restore differing target contents, bypass old
  successful checkpoints, and are reported as `forced_copy` with reason
  `replicate_override`. Force repeats on every resume until reset to 0. Resetting
  restores count-based skipping without changing the retained source snapshot.
- Reproduce equal source/target partner counts with partner 6 missing in target
  and referenced by a target user. Normal verification skips the table; override
  restores source IDs and permits the saved user/partner FK to be restored.
- A forced-copy checkpoint failure rolls back row changes and sequence restart;
  retry succeeds. Forced endpoints replay their M2M operations and keep scoped
  orphan cleanup/FK recovery, unattended backup/gating, and source-ID semantics.

## Scoped M2M orphan cleanup (2026-11-13)

Final suite: **348 tests, 338 passed and 10 optional tests skipped** in 47.512
seconds on an isolated PostgreSQL 16 instance over a private Unix socket. Offline
discovery: **348 tests, 183 passed and 165 skipped**. The CSV subset contains
**111 tests**. Compilation and `git diff --check` passed. Only generated disposable
databases were mutated; no application migration or manual data repair was run.
The temporary test cluster was stopped and removed after validation.

Cleanup runs after the current model/relation operations and before independent
FK restoration. It applies only to eligible M2M operations whose selected
endpoints completed successfully, including count-skipped models. Ordinary M2O
tables, registered model tables, unrelated/excluded relations, and relations with
failed/unfinished selected endpoints are not swept. Count-only verification and
unattended CSV execution remain unchanged.

Coverage includes:

- Reproduce `res_company_users_rel` with users 2951 and 9426 absent from both
  databases. A count-skipped rerun removes only their memberships, preserves
  valid company/user records, and restores `res_company_users_rel_user_id_fkey`.
- Generic custom endpoints: remove links with either/both endpoint records
  missing, including old links left by replacing an endpoint. Preserve valid
  extra links to ignored endpoint models and unrelated invalid M2M/M2O rows.
- Stream more than 1,000 orphan candidates through a server cursor and bounded
  DELETE batches. Each DELETE rechecks endpoint absence and logs only IDs
  actually removed; table OID plus tuple ID avoids collisions across partitions.
- Rollback on cleanup-checkpoint failure or interruption restores link rows and
  removes uncommitted audit files. Retry succeeds without recopying committed
  models. Cleanup failures are reported separately and FK restoration still runs.
- Current and historical cleanup reports retain private 0600 JSONL deleted-ID
  file paths, deleted counts, remaining relation counts, and audit history across
  later no-op retries. Source/target data payload hashes are not introduced.
- Active incoming cascading FKs block cleanup rather than allowing a junction
  deletion to cascade into business records. All verification and deletion tests
  use generated disposable databases; no application migration is executed.

## Count-only verification and unattended CSV execution (2026-11-13)

Final suite: **338 tests, 328 passed and 10 optional tests skipped** in 46.799
seconds, using a private temporary PostgreSQL 16 cluster over a Unix socket.
Offline discovery: **338 tests, 183 passed and 155 skipped**. The CSV subset has
**101 tests**. Compilation and `git diff --check` passed. No application database
was changed, opened for migration, or restarted; database mutations used generated
disposable fixtures only. The temporary cluster was stopped after testing.

- Replace full-content verification with `csv_count_v1`: read source counts from
  the retained extraction manifest and issue target `SELECT count(*)`. Equal
  model/replacement counts skip even if IDs, values, constants, or XML-ID mappings
  differ. No source row projection, normalization, per-row hashing, verification
  SQLite files, or old verification-artifact checks are used to decide skipping.
- Count mismatches retain normal transactional copying and XML-ID mapping.
  Additive M2M skips when target count >= source count; relations replay after
  actually copied selected endpoints to account for changed IDs. Replacement
  post-copy counts must equal source counts; additive post-copy counts equal the
  previous count plus inserted rows. Native constraints/input parsing and source
  extraction-file integrity remain enforced independently.
- Count fixtures intentionally start with differing model counts so copy/mapping
  regressions still exercise actual writes. Tests explicitly cover same-count
  changed IDs/values/defaults, count-only legacy resume without old SQLite files,
  a mocked 29,463,325-row comparison with no source reads or COPY, and additive
  count semantics, mapping retries, sequence behavior, and FK recovery.
- Remove the CSV backup/replication `Continue? [y/N]` prompt. Controller tests
  reject any call to `input()` and verify automatic backup, gating, operations,
  FK restoration, and reopening. The optional explicitly requested extra-action
  menu and the separate non-CSV migration workflow retain their own behavior.

## Both-side table eligibility (2026-11-13)

Final suite: **336 tests, 326 passed and 10 optional tests skipped** in 56.419
seconds, using an isolated temporary PostgreSQL 16 cluster over a private Unix
socket. Offline discovery: **336 tests, 181 passed and 155 skipped**. The CSV
subset contains **99 tests**. Compilation and `git diff --check` passed. Database
mutations were limited to generated disposable fixtures; the cluster was stopped
and removed after validation.

Coverage includes:

- Selected source-only/target-only model rows are automatically ignored despite
  replication flag 1; physical metadata controls eligibility independently of
  the editable CSV `existance` label. Both-side tables still require usable IDs.
- Source-only and target-only M2M relations are excluded before strict endpoint
  binding checks, including stale declarations and a missing source declaration.
  Common relations with one-sided endpoint tables are excluded too. Common
  physical relations with missing target declarations, column mismatches, or
  reversed endpoint roles retain strict failures.
- Reproduce the exact `ab_hr_job_ab_visit_report_report_rel` failure with a
  source-only report model and source-only relation, after deleting one-sided
  CSV rows. Both the fresh run and retained-extraction resume skip the relation,
  copy/verify the common job table, and report warnings without failed operations.
- One-sided-only selections produce warning reports without backup, target
  downtime, or checkpoint writes. Ignored association links and outstanding FK
  restoration remain preserved; historical operations outside the active scope
  do not inflate committed counts. Exclusions appear in JSON/Markdown reports.

Read-only planning of the existing `main19-migrate.csv` and its sidecar succeeds:
**119 selected model tables, 44 eligible M2M operations, 16 excluded relations**.
The reported relation is excluded as `source_only` / `missing_target_table`.
The CSV/sidecar files and application databases were not changed or migrated.

## Content verification across CSV runs (2026-11-12)

Final suite: **326 tests, 316 passed and 10 optional tests skipped** in 53.685
seconds, using a private temporary PostgreSQL 16 cluster with Unix-socket access
only. Offline discovery: **326 tests, 176 passed and 150 skipped**. The CSV subset
contains **89 tests**. Compilation and `git diff --check` passed. No application
database was migrated, changed, gated, or reset; all database mutations used
generated disposable fixtures. The isolated cluster was stopped after validation.

- Format-4 checkpoints adopt identical contents across different plan IDs and
  archive previous format-3/4 state instead of rejecting run ownership. Saved
  success markers and equal counts alone cannot authorize skipping.
- Canonical row-hash multisets compare IDs and all insertable target columns,
  using PostgreSQL composite input and bounded private SQLite indexes. Test
  cases cover equal counts with changed IDs/values, duplicate source IDs,
  numeric precision normalization, varchar length errors without truncation,
  generated columns, binary/JSONB/array/timestamp values, and escaped text.
- Current constants and changed target XML-ID matches trigger selective recopy.
  Additive M2M checks a subset and only inserts missing links, preserving extras;
  matching operations perform no DELETE/COPY and do not rewind sequences.
- Pre-copy verification/mapping errors preserve target rows. After-copy content
  verification catches an INSERT trigger that changes values and rolls back its
  table. References retained before metadata replacement still require existing
  target endpoint records during preparation, never queries during active COPY.
- Incomplete and pre-XML-ID extractions create a fresh generation without
  overwriting original snapshots. Ordinary compatible resumes reuse their source
  snapshot. Reports distinguish verified/copied/additive/failed outcomes and
  retain expected/actual hashes, counts, comparison reasons, and timings.
- Checkpoint archival is transactional; interrupted adoption retries without
  recopying matching data. Outstanding missing FKs survive run transfer;
  malformed history and corrupted verification artifacts are rejected.
- Previous-generation availability recovery requires the same database/OID and
  an unambiguous marker. Unidentified offline targets remain untouched. Wrong
  target identities and schema changes still fail before copying.

## Generic CSV XML-ID relationships (2026-11-12)

Final suite: **300 tests, 290 passed and 10 optional tests skipped** in 64.437
seconds. Offline discovery: **300 tests, 176 passed and 124 skipped**. Compilation
and `git diff --check` passed.

Validation uses a private temporary PostgreSQL 16 cluster with Unix-socket access
only and generated disposable source/target databases. No application database
was migrated, changed, gated, or reset. CSV schema and sidecar versions are
unchanged; older retained extractions without XML-ID snapshots require a fresh
run. The legacy migration path remains unchanged.

Coverage includes:

- Generic stored M2O references to ignored models, including audit user fields;
  exact shared XML IDs with expected models and existing target records.
- Real `res.users`/`res.groups` model names with differing source/target group
  IDs and renamed M2M fields; arbitrary custom endpoints and unidirectional M2M
  declarations work through the same planner.
- Both endpoints selected retain source IDs and replace M2M links; one selected
  maps the ignored endpoint and adds links; neither selected does no relation
  copy. Failed selected endpoint operations block association writes.
- Missing source/target XML IDs, wrong models, dangling records, conflicting
  aliases, multiple aliases resolving to one record, and absence of numeric-ID
  fallback. M2O failures roll back tables; unmatched M2M links warn and skip.
- NULL preservation and target constants bypassing mapping, including unavailable
  comodel metadata. Unavailable M2O endpoints otherwise reject planning. Plain
  integer and nonstored fields are excluded from mapping.
- Frozen source aliases and target snapshots; copying `ir_model_data` cannot
  change decisions mid-run or on a pending retry. Repaired target aliases can
  resolve pending work when target metadata has not been replaced; changed
  committed mappings are rejected.
- Mapping artifact/source snapshot corruption, older retained extraction
  rejection, rollback before a mapped checkpoint commit, and successful retry.
- More than 1,000 IDs across lookup batches; record payload batching bounded by
  both count and bytes; private indexed SQLite artifacts contain identity
  metadata/decisions rather than business payloads. No PostgreSQL staging.

## Target selection diagnostics and table presence (2026-11-12)

Final suite: **269 tests, 259 passed and 10 optional tests skipped**, using an
isolated temporary PostgreSQL 16 instance. Offline discovery: **269 tests,
174 passed and 95 skipped**. The CSV subset has **32 passing tests**.
Compilation and diff checks passed. No migration or application DB writes were
performed; the bound target was queried read-only for selection metadata.

- New exports use metadata version 2 and replace both business-sample columns
  with `available_target_selections_json`; no business sample rows are queried.
- Stored keys come from `ir_model_fields_selection`/`ir_model_fields`, in metadata
  order. Tests cover duplicate keys/shared owners, shared/nonstored/non-selection
  exclusions, empty business tables, unresolved choices as null, and empty maps.
- `existance` distinguishes `source_only`, `target_only`, and `both` using
  physical catalogs, independently of row counts. One-sided table selections
  retain the existing failure before replication; no tables are created.
- Version-1 legacy headers and new version-2 headers remain readable. Conversion
  preserves operational cells, row order, identity/schema binding, and plan ID;
  committed-table resume remains valid. Wrong-target conversion and overwriting
  an existing converted plan are rejected.

Converted the existing `main19_table_plan.csv` into its sibling
`main19_table_plan_selections.csv`, plus matching metadata sidecar, under
`/opt/odoo19/migration-runs/`. SHA-256 verification confirms both original files
are unchanged. All 341 rows and existing operational/other diagnostic cells were
preserved. Presence counts: **95 source_only, 202 both, 44 target_only**.
The new CSV contains 26 target-only selection fields, including two unresolved
dynamic lists shown as null. Its largest cell is **1,986 characters**, versus
the original 576,759-character sample; no new cell exceeds 32,767 characters.

## CSV direct replication (2026-11-12)

Final suite: **263 tests, 253 passed and 10 optional tests skipped**, using an
isolated temporary PostgreSQL 16 instance with Unix-socket access only. Offline
discovery: **263 tests, 172 passed and 91 skipped**. The CSV-focused subset has
**26 passing tests**. Compilation and `git diff --check` passed.

The first shared-server full regression attempt encountered an unrelated Odoo
connection/background-worker race in an existing controller test; the final
suite used an independent instance. An existing CLI assertion was updated for
the three new optional arguments while retaining four required arguments.
Optional real-Odoo clone and legacy opt-ins remain disabled. No application DB
was migrated, reset, or gated; database mutations used generated disposable DBs.

Coverage includes:

- Read-only CSV/sidecar export, exact headers, credential redaction (including
  generic config values), NULL/empty samples, JSON constants, and selection rules.
- Standard/custom replacements with source IDs and no PostgreSQL staging,
  mappings, ORM validation, or user/partner identity prerequisites/reports.
- Explicit shared-value overrides, JSON/false/zero/empty constants, explicit NULL
  instead of SQL defaults, NOT NULL/type failure isolation, and empty source data.
- Replacement/additive M2M operations, retained file corruption rejection,
  committed fingerprint verification, and pending default corrections.
- Incoming CASCADE/SET NULL FKs owned by ignored tables: ignored rows remain
  unchanged; unsatisfied restoration is reported. Composite FKs are captured
  with correct column pairing. A simulated removal failure blocks replacement.
- Target FK recapture after gating, including an incoming CASCADE constraint
  introduced during online backup; stale pre-backup metadata cannot miss it.
- Transactional sequence restart rollback; interruption before marker commit and
  after copy commit; skipped successful work on resume; changed-plan/edit refusal.
- Real controller backup, watchdog reopening, all-zero no-op, early schema drift
  rejection, optional action-only retries, and absence of registry/identity calls.
- Optional directory merging, identical-file reuse, preservation of target-only
  files, and rejection of conflicting content. File actions default to disabled.

### Direct-copy microbenchmark

Three alternating-order staged/direct pairs ran on equivalent generated
databases, each containing **250,001 rows** and a **33,889,312-byte retained COPY
file**. Both variants produced identical sorted target fingerprints.

| Measurement | Staged path | Direct path |
| --- | ---: | ---: |
| Median measured copy-path duration | 1.617 s | 0.923 s |
| Rows written to staging | 250,001 | 0 |
| Total data rows written | 500,002 | 250,001 |

Measured copy-path reduction: **42.9%**. Logical data-row writes decreased
**50%**. This is not a measurement of total physical disk bytes or WAL volume.
The staged baseline explicitly loads/indexes/counts/fingerprints a staging table
before DELETE/INSERT SELECT; the direct path COPYs into the target. Both maintain
the sequence and fingerprint the target. Extraction, backup, FK handling,
checkpoint overhead, and optional files are outside this timed microbenchmark;
the results do not predict complete production migration duration.

Reproduce on an isolated disposable PostgreSQL instance with CREATEDB:

```bash
MIGRATION_PREPARED_TEST_CONFIG=/path/to/test-maintenance.conf \
/opt/odoo19/venv19/bin/python tools/accounting_migration/tests/benchmark_csv.py \
  --rows 250000 --trials 3
```

The harness creates/drops only generated `codex_migration_test_prepared_*` DBs.
The benchmark compares SQL data paths, not the entire former public importer.

## Fingerprint reuse and recovery (2026-11-11)

The offline suite reports **237 tests: 164 passed, 73 skipped**. With disposable
PostgreSQL fixtures enabled: **237 tests: 227 passed, 10 skipped**. Optional
legacy and real-Odoo clone acceptance settings were not enabled. Compilation and
`git diff --check` passed.
No application database, including `dev-central19`, was opened or changed.

- Identical table/ordered-column/filter descriptors share one digest within a
  single operation. Different scopes retain separate hashes; subsequent
  operations and resume validation always perform fresh reads when required.
- Raw XML-ID repair and operations without deferred/attachment scalar fields
  retain full custom-table hashes while committing their actions and markers.
  External relation inserts still execute. Missing or narrower checks fall back
  to fingerprint generation; real attachment-field updates refresh their hash.
- PostgreSQL regressions cover failed checkpoint rollback, interruption after an
  unchanged operation commits, resumed imports without recopying, and rejection
  of external edits. Existing strict-policy and format-2 adoption cases remain.

### Disposable benchmark

Baseline: `a31a650ee3e3249647c92dee8febedad28a12277`. Three alternating-order
baseline/optimized pairs used separate generated databases, each containing
250,001 synthetic header-shaped rows plus the existing relation/attachment
fixtures. Only the live-table workflow is timed: source extraction, staging,
backup, seed construction, resume, and real Odoo registry acceptance are excluded.

| Measurement | Baseline | Optimized |
| --- | ---: | ---: |
| Median workflow duration | 4.431 s | 2.312 s |
| Large-table fingerprint scans | 7 | 1 |
| Median large-table XML-ID phase | 0.698 s | 0.006 s |
| Median large-table external phase | 0.689 s | 0.006 s |
| Median large-table attachment-link phase | 0.707 s | 0.005 s |

The measured workflow reduction was **47.8%**. Every run produced the same
signature across public-table contents, relationship findings, FK outcomes,
fingerprint checks, and operation markers. All resumed without recopying.
This small synthetic benchmark does not predict the 29-million-row application
run or end-to-end migration duration.

Reproduce from the repository root, using maintenance credentials with CREATEDB:

```bash
MIGRATION_PREPARED_TEST_CONFIG=/path/to/test-maintenance.conf \
/opt/odoo19/venv19/bin/python tools/accounting_migration/tests/benchmark_fingerprints.py \
  --baseline-ref a31a650ee3e3249647c92dee8febedad28a12277 \
  --rows 250000 --trials 3
```

The harness loads only the baseline checkpoint/fingerprint modules from Git.
Both variants use the same remaining working-tree code and fixture logic.
It creates/drops only generated `codex_migration_test_prepared_*` databases and
asserts matching results; configuration credentials are never printed.

## Worker locks and standard-table protection (2026-11-11)

**229 tests: 219 passed, 10 skipped**, with disposable PostgreSQL fixtures enabled.
No application database was migrated, reset, stopped, or had its availability
changed. Optional real-Odoo clone acceptance remains disabled.

- A real PostgreSQL validation connection releases metadata transactions and
  relation locks before READY; custom FK DDL then succeeds while the worker waits.
  After GO, the worker observes newly committed values with cleared caches.
- The controller rejects workers that retain an open transaction before gating.
- Standard rows and FK definitions remain unchanged with CASCADE, SET NULL,
  NO ACTION, and composite incoming constraints. Affected custom replacements
  are reported as failed operations; independent custom copies still commit.
- Custom aliases of standard tables and native M2M tables cannot bypass the write
  guard. Attachment/XML-ID operations permit only scoped technical data writes.
- Previously missing protected FK definitions are reported without ALTER, also
  on resume. Existing staging and completed-operation checks remain covered.
- Permitted FK DROP/ADD operations use a five-second PostgreSQL lock timeout.

## Global report-only relationship validation (2026-11-11)

**223 tests: 213 passed, 10 skipped**, with disposable PostgreSQL fixtures enabled.
Compilation and diff checks passed. No application database was migrated or reset.
Optional real Odoo clone acceptance and optional legacy checks were not enabled.

The public CLI now uses `RawImporter` with `raw_references_report_only_v1`.
Historical strict importer tests remain to protect isolated legacy primitives;
their mapping expectations do not describe the public workflow.

New disposable cases verify:

- Raw scalar, Many2one, future integer-rule, and polymorphic IDs commit despite
  missing records/models; real FK restoration failures are nonblocking warnings.
- Required/composite foreign keys do not force NULL placeholders; real NOT NULL
  violations still roll back the affected table while later copies proceed.
- Existing standard records, incoming values, shared associations, and conflicting
  XML-ID models are preserved while custom source IDs are copied.
- Attachments receive collision-free IDs and imported links are remapped without
  duplicate imports on resume.
- User/partner IDs below 7 are excluded from identity comparisons; missing higher
  IDs and actual low-ID FK failures appear in reports without stopping copies.
- Company-property JSON retains raw company/reference IDs and record-specific
  values override defaults.
- Prior mapped-policy commits remain unchanged on adoption of the raw policy.
- ORM audit failures and XML-ID conflicts remain report-only on repeated runs.
- Complete human/JSON/JSONL reports and failed-FK repair SQL are generated.

The controller fixture continues to exercise read-only consistent extraction,
durable staging after preflight failure, resumed copying, target reopening, and
lost post-commit JSON. The registry subprocess is mocked in that fixture.


## Earlier durable staging validation (2026-11-11)

**214 tests: 204 passed, 10 skipped**, with disposable PostgreSQL tests enabled.
The skipped cases require optional legacy settings or an explicitly selected Odoo
clone template. No application database was migrated or had its availability
changed. All table changes and availability gates used generated disposable test
DBs; maintenance connections used `postgres`.

New coverage verifies:

- Staging tables 1/3 commit despite table 2 failing; retry COPY loads only table 2.
- COPY/index/validation rollback, committed data fingerprints, missing tables/PKs,
  source-snapshot mismatches, identity-table handling, and legacy staging adoption.
- Lost staging reports/interruption preserve success markers; completed tables are
  skipped without COPY/index recreation.
- A full controller preflight failure retains `staging_complete`; its next attempt
  performs no staging COPY before continuing the live-table workflow.
- Confirmed reset clears staging-only runs while preserving public records and
  refuses reset after live setup commits.

- Independently committed live tables and atomic table-success markers.
- A failed copy preserving old rows/XML IDs/relations while later tables commit.
- Incoming-reference remapping, external fields, attachment IDs/files and links.
- Circular/self-referencing FK restoration and isolated restoration failures.
- Accepted FK exceptions retained in reports with individual warnings suppressed.
- Target reopening with missing constraints, controlled-interruption restoration,
  interrupted-run continuation, reset rejection, and terminal result revalidation.
- Safe error reports and distinct CLI exit statuses for errors/accepted exceptions.
- Four-table resume: skip tables 1/2/4, correct table 3 mappings/model fields, and
  retry table 3 alone, including newly eligible references and attachments.
- Retrying failed external updates without recopying data, third-run no-copy
  behavior, and rejection of edits/mapping changes affecting completed tables.
- Original format-2 marker adoption and lost-result recovery from database markers.
- The shipped mapping preserves accounting tracking `je_line` as an integer,
  including absent journal-line IDs, zero, and NULL, through a committed table copy.

The controller fixture continues writing through a separate source connection and
checks that imported values come from the consistent read-only snapshot. Its
registry worker is mocked; fresh-registry clone acceptance was not enabled for
this change. Python compilation and `git diff --check` are also required.

The public controller now uses run format 2 and the independent table workflow.
Atomic importer primitives remain available to historical regression fixtures.
Table operations now resume from their success markers after setup commits; the
original extraction and captures remain authoritative.

## Historical implementation results

Optional reset validation (2026-11-11): **184 tests, 174 passed and 10 skipped**,
with disposable PostgreSQL tests enabled. Odoo clone acceptance and optional
legacy checks were not enabled for this CLI/reset change. Compilation and
`git diff --check` passed. No application database was reset or migrated.

Reset coverage includes startup help, default resume dispatch, help-only behavior,
error recovery commands, directory identity/symlink checks, cancellation, active
lock rejection, committed-checkpoint rejection, preservation of public records and
unrelated directories, partial filesystem cleanup/retry, and repeat reset.

The public entry point now selects only the prepared-target workflow. The retired
initializer is isolated in `legacy_migrate.py`, with direct CLI execution disabled;
its historical tests still exercise the old primitives independently.

Validation performed during implementation:

- Python compilation and `git diff --check`.
- Entire regression suite: **177 tests, 168 passed and 9 optional legacy checks
  skipped**, with both new PostgreSQL and Odoo acceptance suites enabled.
- Offline discovery also passes without any database access; the opt-in
  database-backed suites are skipped unless explicitly enabled.
- Read-only registry metadata inspection of the prepared Odoo 19 database.
- Real DELETE/COPY/mapping/attachment operations exclusively in generated,
  disposable PostgreSQL databases.
- Fresh Odoo 19 registry acceptance on a generated disposable clone created by
  read-only `pg_dump` of the explicitly selected prepared target.

No migration, source blocking, or target availability change was performed against
`abdinpharmacies` or `dev-central19`. The Odoo template database was read only.
Generated test databases were removed after testing.

## Historical primitives and retained coverage

The retained importer/helper fixtures and current controller tests cover:

- Shared persistent `ab*`/`abdin*` selection, omissions, and transient/view exclusion.
- Source user/partner ID containment for IDs >= 7 with extra target IDs allowed.
  Missing IDs 5/6 pass both validators; missing ID 7 blocks both. Full low-ID
  metadata and audit user 1 mappings remain intact. Stable-key/password extraction
  overrides for users are forbidden.
- DELETE + COPY + XML-ID updates in one transaction, preserved source IDs,
  original target `noupdate` flags, and source-only aliases.
- Incoming standard/target-only scalar fields and relation rows, including
  `ON DELETE SET NULL` and cascade FKs. Target credentials are not duplicated into
  scalar-reference capture tables.
- Rejection of replacement that would erase prepared associations in a shared
  relation table, including an extra target user's links.
- Reviewed field/selection conversions and structural mapping of renamed
  `ir.model.fields` references.
- Arabic translation conversion and required NULL rejection.
- Company-dependent JSON values keyed by mapped target company IDs, including
  record-specific values overriding defaults.
- External standard-ID mapping without copying standard records.
- Attachment ID collisions, owner/link mapping, available files, missing-file
  records, late rollback after file publication, and idempotent retry.
- Online target edits detected by imported-table fingerprints. Existing lookup
  identity changes are guarded by separate mapping fingerprints.
- Target reopening after errors and after controller SIGKILL through the watchdog.
- Source catalog/data connections are read-only; source ownership/session control
  is not requested. An unavailable source never gets an availability gate.
- Full controller execution starts from a prior failed-ID run, tolerates missing
  low IDs, refreshes source IDs after a successful identity checkpoint and failed
  extraction, and preserves the same run directory.
- A separate source client stays connected and writes during migration. Copied
  values reflect the consistent snapshot rather than a later committed update.
- Lost JSON report after a committed terminal table result, cancellation, reuse of
  completed extraction before live setup without a source data connection, and
  repeat retrieval of a saved result without duplicate attachments. Source access stays available
  after failures, cancellation, success, and repeat runs. Old availability reports
  are left unchanged and ignored.
- The read-only ORM worker opens its cursor before target blocking and executes
  its probe inside the offline window. The real Odoo acceptance fixture replaces
  `ab_customer_contact_way` IDs and verifies reads from a fresh registry.

## Shared fields and progress coverage

- Populated source-only scalar fields (including vendor-like references) and cached
  M2M fields are skipped before reference resolution. Raw values remain in staging.
- Source-only attachment metadata is skipped; attachments referenced exclusively
  by skipped fields are excluded while owned/shared-linked attachments are retained.
- New extraction skips source-only M2M tables; cached extraction filtering requires
  no file rewrite. Required target-only fields still stop before replacement.
- Byte wrappers preserve COPY payloads exactly. COPY percentages require measured
  totals; INSERT SELECT operations do not invent a percentage.
- Slow console output does not block producer updates or file output. Logging
  exceptions remain nonfatal; approval pauses and completed phases reject stale
  monitor samples.
- Statistics are scoped to database/PID/start time. The watcher reads through
  `postgres` while a disposable target is blocked and leaves its availability
  unchanged. No raw SQL values are emitted.

## Running tests

Offline only:

```bash
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -p 'test_*.py'
```

New PostgreSQL fixture tests, using a config with maintenance access and CREATEDB:

```bash
MIGRATION_PREPARED_TEST_CONFIG=/path/to/test-maintenance.conf \
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -p 'test_prepared*.py'
```

Add read-only dumping of an explicitly selected Odoo 19 template for real registry
acceptance on a disposable clone:

```bash
MIGRATION_PREPARED_TEST_CONFIG=/path/to/test-maintenance.conf \
MIGRATION_PREPARED_ODOO_TEMPLATE_DB=YOUR_PREPARED_ODOO19_TEMPLATE \
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -p 'test_*.py'
```

These fixtures connect to `postgres` and generated
`codex_migration_test_prepared_*` databases. Only the explicit Odoo acceptance
fixture reads the selected template using pg_dump. It never modifies the template.
No pre-existing application database is dropped. Config passwords remain in private
temporary files/environment and are not printed or committed.

## Limits

This is not a complete Odoo 15 production migration rehearsal. Large E-Plus tables,
full filestore throughput, every custom field adapter, and every branch role were
not exercised against the production dataset. The Odoo acceptance clone tests a
representative installed custom model; PostgreSQL fixtures test the broader
conversion and recovery paths.

Branch checks sample configured departments and models with direct stored branch
fields. They are not proof of every module's security policy. Reviewed manager
exceptions are configured through `branch_manager_xmlids`; unexpected broad access
blocks final validation for review.

Source-only/nonstored target fields are skipped and reported. Incompatible shared
fields, missing custom prerequisites used by shared references, retired report
references in shared fields, unsupported shared reference formats, or required
external fields can still require reviewed preparation. The tool never invents a
value or weakens required constraints.

Missing source user/partner IDs >= 7 must still be prepared separately; additional
target IDs and missing IDs below 7 are permitted. Source availability is never
changed by the script. Extraction is a point-in-time view and does not include
source changes committed after that snapshot begins.
