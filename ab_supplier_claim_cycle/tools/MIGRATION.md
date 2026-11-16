# Supplier claim transfer

These are offline maintenance tools, not an installed addon or RPC interface.
Run with the Odoo virtualenv. They support legacy `19.0.4.x` and dynamic
`19.0.7.x` sources and a dynamic `19.0.7.1.0` target.
Update/install the module from current code before importing: its inherited form
view exposes department notes/dates only when populated or granted by a stage.
Their write permissions continue to come entirely from the dynamic workflow.

## Boundaries for the first transfer

- `abdinctrl` / `hr_db` is **read-only**. The exporter uses a PostgreSQL
  repeatable-read, read-only transaction and reads attachment files. It never
  opens an Odoo registry, writes a remote script/file, changes a module, or
  restarts a service. Python bytecode writing is disabled remotely.
- Do **not** create a new backup of `hr_db_dev`: the operator already has one.
- All bundles, reports, test databases, workflow creation, and imports are local.
- Production reinstall/import is a separate, later operator-authorized operation.

## Source export

From `/opt/odoo19/hr`:

```bash
PY=/opt/odoo19/venv19/bin/python
TOOL=ab_supplier_claim_cycle/tools/claim_transfer.py
RUN=/opt/odoo19/migration-runs/supplier_claim_20261116
$PY "$TOOL" export --ssh abdinctrl --bundle "${RUN}_source"
$PY "$TOOL" preflight --bundle "${RUN}_source" --report "${RUN}_preflight.json"
```

A bundle directory must not already exist. It contains `data.json`, a hashed
`manifest.json`, and content-addressed `blobs/`. Keep it private. The bundle is
complete only when its manifest exists and all hashes/counts validate. A failed
export leaves an unusable directory, never a valid partial import.

Preflight resolves cost centers by unique code, users by login, partners through
mapped users or unique email/ref, and companies by unique VAT/name. It rejects
missing or ambiguous matches. Legacy claims do not have a company field, so the
source must have exactly one company. For exceptional mappings provide
`--mappings /private/mappings.json`, for example:

```json
{"users": {"SOURCE_ID": 123}, "companies": {"SOURCE_ID": 1}}
```

Values are validated target IDs, not source IDs. Never put credentials in bundles
or mapping files. A single company's name/VAT or a mapping verifies its identity;
no numeric cross-database identity is assumed.

Explicitly resolved user logins are retained as migration provenance. On return
to the original database, its UUID **and** database name must match before those
original logins are used. This handles a user whose local login differs without
renaming that account or relying on equal numeric IDs.

## Local rehearsal and import

Run isolated integration tests before touching local claim data. The existing
module test suite covers workflow business rules and record-rule access. The
new tool tests cover amount parsing, mapping, integrity failures, imports,
permissions, continuation, and idempotency.

```bash
$PY -m unittest discover -s ab_supplier_claim_cycle/tools -v
CLAIM_TRANSFER_TEST_DB=supplier_claim_migration_test_20261116 \
  $PY -m unittest discover -s ab_supplier_claim_cycle/tools \
  -p test_transfer_integration.py -v
```

The integration test requires an installed **disposable** database whose name
starts with `supplier_claim_migration_test_`; fixture transactions roll back.

Import defaults to rollback. `--replace-claims` clears target claim data and
workflow definitions only, including related chatter/audit/documents and
migration identities. It does not clear suppliers, users, or unrelated HR data.
The target claims table is locked while importing. Keep users out of the local
claim app during replacement.

```bash
$PY "$TOOL" import --bundle "${RUN}_source" --replace-claims \
  --confirm-database hr_db_dev --report "${RUN}_dry_run.json"
$PY "$TOOL" import --bundle "${RUN}_source" --replace-claims \
  --confirm-database hr_db_dev --report "${RUN}_import.json" --commit
$PY "$TOOL" verify --bundle "${RUN}_source" --report "${RUN}_verify.json"
```

Each import is one atomic transaction: failure rolls back database changes.
Odoo's filestore garbage collector handles unreferenced files from failed runs.
Repeated identical imports verify existing records and skip creation. A changed
bundle from the same source, or changed imported data, is rejected rather than
silently overwriting it. For a deliberate later full replacement, use both
`--replace-claims --replace-source-snapshot`; do not delete the fingerprint alone.

## Workflow behavior

- Cash: Supplier Accounts → Secretarial Closure.
- Check/bank transfer: Inventory → Purchasing → Supplier Accounts → Bank Accounts
  → Secretarial Closure.
- Source department memberships configure approvers. Only active internal users
  are approvers. Historical department memberships map to Workflow Participant;
  Secretarial, Reviewer, and Administrator memberships retain their XML IDs.
  Approvers continue to come from the source stage configuration/department
  metadata, not from recreated department groups.
- Drafts without a payment method remain drafts without a selected workflow.
- Rejections resume their rejecting stage; deferrals retain original dates,
  including overdue dates. Ready-to-close claims wait at Secretarial Closure.
- Archived records remain archived. Existing ahead-of-current approvals survive.
- Text amounts accept validated thousands separators and up to two decimals;
  `7,156.` becomes `7156.00`. Unsupported/zero/negative values stop preflight.
- Extra decimal places are rejected by default. Only use `--amount-policy round`
  after agreeing to HALF_UP cents conversion; pass it to preflight, import, and
  verify. The report lists each adjustment and total difference, and the original
  amount is preserved in a migration audit note.
- Source `cheque_attachment` becomes `supplier_cheque_attachment`. Inline source
  files have no upload history; their first imported document snapshot is clearly
  labeled with migration time, not a fabricated original upload time.
- Original history and chatter retain actors/dates. Missing audit-linked messages
  are generated once; original ordinary chatter is retained. Outbound mail and
  notification dispatch are not replayed. Attachment access tokens are not copied.
- Legacy payment changes that alter routing mid-review and special editing
  exceptions are intentionally not implemented. Select the correct payment route
  before submitting new claims.

## Prepare the return bundle (local only)

Find the `claim_transfer_…` namespace in `ir_model_data`, then export only that
migration's claims. This prevents accidentally returning development-only claims.

```bash
$PY "$TOOL" export --bundle "${RUN}_return" \
  --source-python /opt/odoo19/venv19/bin/python \
  --source-config /opt/odoo19/config/hr19.conf --source-db hr_db_dev \
  --source-filestore /opt/odoo19/OdooLocalData/filestore \
  --namespace claim_transfer_REPLACE_WITH_ACTUAL_NAMESPACE
```

Test this bundle in an isolated clean dynamic database and compare all imported
fields, history, chatter, and binary content. It preserves dynamic configuration
and runtime stages without converting back to the hardcoded schema.
Both migration-owned workflow definitions are included even if one has no claims
(for example the cash workflow in this source snapshot).

## Later production cutover — do not run in the first migration

1. Coordinate a claim write freeze and take a fresh read-only production export.
   The current rehearsal snapshot does not include subsequent live changes.
2. Deliberately replace/rehearse local claim data from that final snapshot and
   verify it; export a fresh namespace-filtered dynamic return bundle.
3. Deploy the dynamic module code. The operator manually reinstalls the module
   on production. Merely reinstalling old code cannot accept dynamic records.
4. Put the tool and bundle on the target only during that separately authorized
   phase. Run `preflight`, rollback `import`, committed `import`, and `verify`,
   specifying production config, database, Odoo root, and exact database confirmation.
5. Reopen claims only after reconciliation. Keep the operator's rollback material
   (matching database/filestore/code) and reports.

The first-transfer command never implements any of these production mutations.

## Four-role security upgrade

Upgrade existing dynamic databases to 19.0.7.1.0 with `-u ab_supplier_claim_cycle`.
No reinstall or claim reimport is required. Existing department members retain
Participant access, but can read only claims assigned to them, with complete
workflow/history/document access for those claims. The module supplies read-only
cost-center access and retains company restrictions. Unknown external security
dependencies cause the upgrade to stop.

The target-version check requires 19.0.7.1.0; old 19.0.4.x/19.0.7.x bundles remain
readable. New exports contain only the four generic security roles.
