# Bulk migration and resume validation

The user requested a script update and will run the migration manually. No source
migration, destination initialization, database writes, or database-backed tests
were executed while implementing the fresh bulk workflow.

Checks performed (109 tests passed; four opt-in PostgreSQL/Odoo tests skipped, including optional SQL syntax checks in the passing set):

- Python compilation of the new entry point, COPY extraction module, bulk loader,
  and isolated worker.
- Offline unit tests covering four-argument parsing, old-option rejection,
  same-source/target rejection, refusal of an unowned existing target before any writes,
  E-Plus scope without date filters, group-field renaming, binary-safe COPY output,
  generated ID/translation conversions, unknown populated-column rejection, and
  explicit-column set-based insertion.
- Existing adapter/compatibility unit tests.
- Delegated source-language discovery, explicit English/Arabic activation,
  additional languages, null/duplicate preferences, schema rejection, translation
  failure reporting, and verification that contact/user preferences are not written
  by language setup.
- Mocked orchestration through success, failure, and interruption: connections
  stay enabled, no database sessions are terminated, and initialization/language
  errors stop before extraction. No real database connections are made.
- COPY-order regression: actual export and staging-loader code exercised with
  mocked database cursors and real temporary COPY/JSON files. Nonalphabetical
  column order survives sorted JSON serialization. Invalid/missing/duplicate/
  unknown columns and old manifests are rejected before staging SQL executes.
- PostgreSQL SQL syntax parsing of generated representative statements using
  `pglast` installed only under `/tmp/accounting-migration-sql-check` for testing.
  It is not a runtime dependency.

- Concurrent progress tests cover blocked console output with independent file
  output, bounded/coalescing queues and drop notices, broken sinks, stale monitor
  samples, ETA thresholds, remote worker events, read-only monitor configuration,
  PID-scoped statistics, sparse/negative keysets, nonadvancing batch rejection,
  explicit SQL columns, and absence of per-batch commits.
- No migration was started or database changed for the logging implementation.
  Real PostgreSQL throughput and monitor behavior remain runtime checks.

Run the tests without touching databases:

```bash
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -p 'test_*.py'
```

The optional SQL parser test skips when `pglast` is unavailable. To include it with
the temporary checker already installed on this machine:

```bash
PYTHONPATH=/tmp/accounting-migration-sql-check \
/opt/odoo19/venv19/bin/python -m unittest discover \
  -s tools/accounting_migration/tests -p 'test_*.py'
```

Not yet established for the new bulk path:

- End-to-end migration against a real Odoo source/target pair.
- Measured throughput on a large table.
- Database-enforced behavior of every generated conversion and default.
- Runtime registry/view/permission acceptance or browser interaction.

The script performs automated runtime checks during the user's manual run and
writes `verification.json`. Unsupported data/schema cases fail explicitly and
leave the new target incomplete but connectable. A passing unit suite must not be described as a
completed or fully validated database migration.

## Resume implementation

Offline recovery tests cover unique owned-run discovery, identity/fingerprint
mismatches, active target sessions, legacy staging evidence, staged schema/count/
index checks, committed-table skips without file reads, COPY failure before table
commit, mapping commit followed by business rollback, mapping reuse, and business
checkpoint reuse. They also cover stale JSON reports after completion, complete
extraction reuse without a source connection, interrupted-extraction archival and
restart, and aggregated validation errors. Checkpoint tests use fake cursors; they
do not establish database-enforced behavior by themselves.

`tests/test_resume_postgres.py` is opt-in and was **not run**. It requires an
explicit `MIGRATION_RECOVERY_TEST_DSN` naming a disposable database with prefix
`codex_migration_test_`. It creates only a uniquely named test schema, tests real
COPY/DDL/checkpoint rollback and commit persistence after reconnect, and removes
that schema afterward. It never reads Odoo connection configs.

The addon change introduces no user-facing strings: existing English labels and
both Arabic translation files are unchanged. Source inspection confirms that user
account permissions follow the assigned accounting group. Runtime verification
now rejects any unassigned user receiving accounting authorization rows, and the
existing field-by-field comparison checks preservation of NULL group IDs. Neither
the targeted addon upgrade nor those runtime Odoo checks have been executed here.

The legacy `migrate_test3` recovery path has not been exercised against the real
database. The first manual resume will verify and adopt its staging before reuse;
its previously rolled-back mapping cannot be recovered and will run again.


## Both authorization groups optional

- Upgrade detection tests cover either column required, both required, both
  optional, and tables not yet installed. Post-upgrade validation checks both ORM
  declarations and physical columns, including missing-column rejection.
- Offline tests cover NULL-preserving group-ID expressions, early validation of
  nullable groups, continued rejection of missing required allowed-field references,
  and rejection of either authorization type on a user without an accounting group.
- Existing recovery tests still pass: committed COPY is skipped, validation
  precedes mapping, and committed mappings survive later business-load failure.
- No UI text changed, so existing English labels and Arabic translations remain
  unchanged. No live addon upgrade, migration, or database-backed test was run.


## Strict business IDs and target-seed reconciliation

The interrupted E-Plus-only optimization is superseded: all copied business/master
models use preserved IDs, and only technical lookup models use explicit maps.
Format-1/2 mapping metadata can be archived before any business commit; old-policy
committed business/runtime results are refused. Tests cover swaps, unrelated seed
collisions, protected root identity, contradictory matching, ID-range exhaustion,
NULL-preserving reference resolution, adapter SQL syntax, XML-ID scope/conflicts,
and old-checkpoint refusal. Recovery tests cover rollback and reuse of the strict
plan. No source business IDs are allocated or offset.

Three PostgreSQL tests are opt-in via `MIGRATION_RECOVERY_TEST_DSN`: transaction
checkpoints, resolver equivalence/synthetic benchmark, and seed swaps with FK,
JSON and XML-ID reference updates plus rollback. A fourth test in
`test_strict_odoo.py` checks an already migrated disposable Odoo database in a
fresh isolated registry, using explicit `MIGRATION_ODOO_TEST_CONFIG`,
`MIGRATION_ODOO_TEST_DB`, and `MIGRATION_ODOO_TEST_STAGE`. All four were skipped.
No real seed relocation, addon upgrade, migration or benchmark was executed.

Source-only business XML-ID aliases restore with noupdate=true; existing target
flags are unchanged and original source flags remain in staging/export. This
protects imported aliases from normal module cleanup without replacing Odoo 19
technical definitions. Effective permission behavior remains a runtime acceptance
check, not something established solely by the offline test suite.
