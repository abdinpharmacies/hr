# Custom-model migration into a prepared Odoo 19 target

Run with the Odoo 19 virtual environment. Both database names are arguments:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/migrate19/tools/accounting_migration/migrate.py \
  --source-config /opt/odoo15/config/abdin15.conf \
  --source-db YOUR_SOURCE_DB \
  --target-config /opt/odoo19/config/migrate19.conf \
  --target-db YOUR_PREPARED_TARGET_DB
```

These four arguments are required. `--help` never connects to a database.
There are no automatic-confirmation, database-creation, or installation options.

**Source access is read-only.** The script never enables/disables the source,
terminates its sessions, or requires source ownership/session-control privileges.
Normal source clients may remain connected and continue writing. Only the target
is temporarily unavailable during approved checkpoint processing.

The target must already contain its Odoo 19 modules, standard business records,
technical metadata, and security configuration. The tool does not install or
upgrade modules, copy credentials/memberships, or import standard business tables.
Existing data in the selected custom tables is disposable and will be replaced.

## Scope and ID rules

- Select persistent custom models beginning with `ab`, including `abdin*`, present
  in both source and target. Technical model metadata determines physical tables;
  a table prefix alone never authorizes deletion.
- Report missing source models, rather than installing their modules. Preserve
  target-only models. Skip transient/abstract models and SQL views.
- Preserve source custom IDs, including custom-to-custom relationships.
- Require source user and partner IDs **7 and above** to exist in the target;
  extra target IDs are allowed. IDs below 7 (including 5 and 6) are skipped by
  both the initial and later checks. Reports show checked/skipped/missing counts.
- Keep all source user/partner IDs in extraction metadata and reference maps.
  Skipping an ID check never discards its references: unresolved populated
  references still stop preflight. Audit users such as ID 1 continue to map.
- Compare IDs only, including inactive records. Equal IDs are accepted as equal
  identities without comparing names, logins, or emails.
- Standard IDs other than users/partners are resolved through XML IDs, structural
  model/field identities, reviewed unique keys, or explicit mappings.
- Do not guess security groups by display name or treat equal standard IDs as
  identity. Missing/ambiguous mappings stop processing.

## Checkpoints and availability

| Checkpoint | Operations committed together |
| --- | --- |
| 1. Identities | Validate source user/partner IDs >= 7; save run metadata and ID staging. |
| 2. Custom data and XML IDs | Stage extraction; preflight; DELETE selected data; COPY adapted rows; restore incoming references; repair custom XML IDs; validate constraints. |
| 3. External references | Populate deferred custom fields and M2M links to existing Odoo records. |
| 4. Attachments | Import scoped attachment records, copy available files, restore attachment fields/M2M links. |
| 5. Validation | Record activity import as skipped; compare values/links; run read-only fresh-registry and branch checks; mark complete. |

Every unfinished checkpoint asks `Continue? [y/N]` while the target is online.
Only `y`/`yes` starts processing; Enter, no, or EOF cancels. Source availability
is never changed, including after errors or cancellation. Each approved checkpoint blocks new target
connections and terminates its other sessions. Migration connections are opened
before the target gate closes. The target is reopened after commit or rollback,
before the next question. PostgreSQL and other databases are never stopped.

DELETE, COPY, and XML-ID repair share one checkpoint: the target never returns
online between those stages. Custom records with nullable external fields are
incomplete until the subsequent mapping/attachment checkpoints. Online access
between checkpoints does not mean the migration has finished. Changes to imported
data between checkpoints can invalidate recovery; the tool detects changed
fingerprints and stops instead of silently overwriting them.

An independent watchdog restores target access after controller failure, including
SIGKILL. It controls only the target. Database/server outages can prevent
immediate recovery; inspect `availability.json` and `watchdog.log`, restore server
access, and rerun. A target disabled outside this run is not automatically adopted.

## Extraction, preflight, and backup

Source ID discovery and extraction use the same read-only, repeatable-read
transaction. This consistent PostgreSQL view does not change source records or
block normal writes. Changes committed after the snapshot begins are outside that
extraction; no incremental synchronization is performed. Private COPY files retain
its data for recovery. Source business/schema/XML-ID tables, availability settings,
and other sessions are never changed.

The extraction includes selected custom rows and links, scoped attachment rows,
lookup metadata, user/partner IDs, translations, and property values. Metadata may
be staged privately but is not copied into public standard tables. No source
passwords or user credentials are extracted.

Only shared stored fields are imported into public target models. Existing
explicit rename mappings are honored. Source-only or nonstored target fields are
skipped even when populated, across every copied model, M2M field, and attachment
metadata field. Skipped fields and reasons appear in `preflight.json` and checkpoint
reports. This is generic, not a special case for `vendor_id`.

Raw extraction files remain unchanged and retain source-only values. Cached
snapshots use the same filtering policy; no re-extraction or target reset is needed.
Attachment owner records remain eligible, but links existing only in skipped fields
cannot pull unrelated attachments into the import.

Before deleting, validate shared-field conversions, required values, relationships,
incoming references, and XML-ID identities. Incompatible shared fields or unresolved
shared references still stop safely. Required external fields that
cannot remain empty also stop; required constraints are not weakened and no
placeholder IDs are invented. Historical prices and inventory quantities are not
recalculated.

A verified full target backup is created online immediately before the first
replacement checkpoint enters its offline window. It is retained as
`before_import.dump` with a SHA-256 manifest. Database transactions provide the
exact rollback boundary for checkpoint failures. The backup records the earlier
online backup snapshot; it is not a substitute for the transaction rollback.
The source filestore is only read; resolved source/target roots must not overlap. A target filestore baseline path is recorded,
and existing files are never overwritten with conflicting content.

Incoming target references are matched before deletion using captured target XML
IDs, reviewed unique keys, or explicit mappings. A matching numeric ID alone is
insufficient. Incoming FK definitions are removed only within the replacement
transaction to prevent cascading deletes/SET NULL on standard records; original
constraints and references are restored and validated before commit. Standard
scalar capture retains only row IDs and affected fields, not copies of credentials.
Shared relation tables cannot erase existing prepared standard/target-only
associations; incompatible rows stop preflight.

## Mapping configuration

`mappings.json` retains reviewed field/selection, XML-ID, integer-link, polymorphic, and
source-model aliases. The prepared workflow additionally reads
`prepared_rules.json`:

```json
{
  "format": 1,
  "stable_keys": {"res.currency": "name", "res.country": "code", "res.lang": "code"},
  "external_ids": {},
  "incoming_ids": {},
  "ignore_fields": {},
  "branch_manager_xmlids": {}
}
```

- `external_ids`: model -> source ID -> reviewed existing standard target ID.
- `incoming_ids`: custom model -> old target ID -> replacement source custom ID.
- `stable_keys`: reviewed, non-null unique identity column; ambiguity blocks.
  Security groups cannot use this strategy.
- `ignore_fields`: model -> field -> explicit reason for excluding that field.
- `branch_manager_xmlids`: model-name glob -> reviewed manager group XML IDs that
  bypass the representative branch audit. System administrators are checked first
  and bypass it automatically. Configure applicable manager/regional-manager
  groups before starting; this setting never changes permissions or memberships.
  For example, `"ab_hr*": ["ab_hr.group_ab_hr_manager"]` is appropriate only when
  that group is authorized for those models. Undeclared cross-branch access is
  reported for review rather than assumed to be authorized.

For example, `"incoming_ids": {"ab_example": {"7": 13}}` declares that old target
custom record 7 represents source custom record 13. This is not seed relocation:
the selected target custom rows are deleted and replaced, and references are
restored to source IDs.

Source-to-target lookup maps are fingerprinted too. Changes to existing XML-ID or
stable-key identities between checkpoints stop before later writes.

Rules and schema fingerprints bind to the run. Do not edit mappings beneath a
committed run and expect automatic adoption: incompatible changes stop. Prepare
reviewed rules before starting, or explicitly recover/restore a failed target
before starting a separate migration attempt.

## XML IDs and attachments

For copied custom models, use source `(module, name, model, res_id)` identities and
exclude module `__export__`. Match `(module, name)`, verify the model, and set
`res_id` to the copied source ID. Do not extract numbers from XML-ID names or copy
`ir_model_data.id`. Preserve unrelated aliases and existing target `noupdate` flags;
new aliases use `noupdate=true`. Unresolved/conflicting aliases stop replacement.

Import attachments owned by copied records or explicitly linked by their stored
fields/M2M tables. Unrelated attachments remain untouched. Allocate collision-free
target attachment IDs, persist a map, and restore custom attachment links. Resolve
owner/user/company references rather than assuming standard IDs match.

Source and target filestores use their respective `data_dir/filestore/DB_NAME`.
Verify available files, copy through temporary files, publish atomically without
overwriting a racing file, and fsync before commit. Reuse identical existing files.
Missing source files keep their database records and original metadata and appear
in `attachments.json`. Inline binary and URL attachments are retained. A rollback
may leave verified files, which retry safely reuses.

Activity import is intentionally not implemented. Inspection found no source
activities for custom models; reports retain the actual extraction count and mark
activity import skipped. Chatter messages/followers are not imported.

## Resume

Repeat the same four-argument command to resume the same target. Run directories
are private under `/opt/odoo19/migration-runs/`; the command prints its exact path.
Checkpoint data and markers commit atomically in the target. A committed database
marker is authoritative even if interruption prevented its JSON report being written.

A failed ID check does not require a new target or run directory. When extraction
is incomplete, retry opens a fresh read-only source snapshot and refreshes saved
ID inputs. If source IDs changed after a previously successful identity checkpoint,
the script asks to revalidate that checkpoint before extracting. Prior ID lists
are archived. Only private staging ID tables are refreshed; standard target user
and partner records are never copied or replaced.

Completed extraction is reused without opening a source data connection; a
read-only catalog query verifies source database identity. Once custom data has
committed, the original complete extraction is mandatory. Missing/corrupted files
stop recovery rather than mixing data from another snapshot. Incomplete extraction
files are archived before restarting extraction.

Source availability is always managed by the operator, never by this script. An
unavailable source produces a read/access error when new extraction is required;
no activation or deactivation is attempted. Historical `source-availability.json`
files from the retired policy are retained unchanged and ignored by the runner.
Current result/failure reports describe source access as read-only.

If target recovery is blocked by a server outage, reconnect to `postgres` on the
target server and review its run marker before manually restoring target access.

Useful private diagnostics include `id-validation.json`, `preflight.json`,
`snapshot.json`, `failure.json`, `availability.json`,
`watchdog.log`, `metadata.log`, `orm-validation.log`, and `verification.json`.
`failure.json` records safe error type/SQLSTATE/table/column/constraint metadata,
not SQL parameter values. Store run files/backups as confidential data.

The retired controller is isolated in `legacy_migrate.py`, whose CLI is disabled.
Legacy initialization/seed-relocation libraries remain for historical regression
tests; the public `migrate.py` entry point never dispatches to that workflow.
See `VALIDATION.md` for fixture coverage and remaining rehearsal limitations.

## Progress and live observation

The runner emits stage labels and periodic updates every five seconds. Staging
COPY shows server rows processed against the retained manifest total, bytes, table
number, percentage, and elapsed time. File bytes read are labelled separately from
server rows loaded. Index stages show PostgreSQL counters when available. Backup
shows file size/elapsed time; validation and INSERT SELECT operations use phase
heartbeats rather than invented percentages. Rows remain pending commit until the
checkpoint commits.

Output is asynchronous and bounded. Slow/broken output or unavailable statistics
cannot stop the migration. Monitoring uses its own read-only connection to
`postgres`, so it works during target offline windows without sharing the writer
cursor or changing source availability. Periodic console output pauses for approval
prompts. Private `progress.json`, `progress.jsonl`, and `migration.log` files are
written inside the run directory. SQL parameters and business values are not logged.

Observe an already running migration from a second terminal without restarting it:

```bash
/opt/odoo19/venv19/bin/python tools/accounting_migration/watch_progress.py \
  --target-config /opt/odoo19/config/migrate19.conf \
  --stage /opt/odoo19/migration-runs/YOUR_RUN_DIRECTORY
```

Use `--once` for one observation. The observer verifies database/PID/start-time
identity, reads PostgreSQL statistics and retained metadata only, and never changes
data or availability. No registered backend does not mean migration succeeded;
check the migration terminal and verification report. Integrated logs apply on the
next launch; the watcher can observe older active processes.
