# Prepared-target migration validation

## Results

The public entry point now selects only the prepared-target workflow. The retired
initializer is isolated in `legacy_migrate.py`, with direct CLI execution disabled;
its historical tests still exercise the old primitives independently.

Validation performed during implementation:

- Python compilation and `git diff --check`.
- Entire regression suite: **167 tests, 158 passed and 9 optional legacy checks
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

## Coverage

The prepared workflow tests cover:

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
- Lost JSON report after a committed replacement, cancellation, completed-snapshot
  resume without a source data connection, completion, and a repeat run that skips
  committed phases without duplicate attachments. Source access stays available
  after failures, cancellation, success, and repeat runs. Old availability reports
  are left unchanged and ignored.
- The read-only ORM worker opens its cursor before target blocking and executes
  its probe inside the offline window. The real Odoo acceptance fixture replaces
  `ab_customer_contact_way` IDs and verifies reads from a fresh registry.

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

Some populated source-only fields, missing custom prerequisites, retired report
fields, unsupported reference formats, or required external fields can require a
reviewed adapter/preparation change before replacement. The tool stops instead of
inventing a value, weakening required constraints, or dropping records silently.

Missing source user/partner IDs >= 7 must still be prepared separately; additional
target IDs and missing IDs below 7 are permitted. Source availability is never
changed by the script. Extraction is a point-in-time view and does not include
source changes committed after that snapshot begins.
