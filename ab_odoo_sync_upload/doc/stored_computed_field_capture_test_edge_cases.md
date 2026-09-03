# Stored Computed Field Capture Test Edge Cases

## Scope

This document lists edge cases for a complete test suite around upload snapshot
capture through:

- `Environment.add_to_compute`, used as the semantic signal that Odoo scheduled
  stored computed fields for recomputation.
- `BaseModel._write_multi`, used as the persistence-level safety net when stored
  computed values are flushed to PostgreSQL.
- The transaction-scoped collector in `env.cr.precommit.data`, used to
  deduplicate records and emit one final snapshot per source record.

The suite should prove that upload source records are captured exactly once with
their final transaction state, while excluded, non-stored, virtual, rollback, and
recursive cases are ignored.

## Common Fixtures

- A configured active upload source model with normal stored fields.
- A configured active upload source model with stored computed fields depending
  on fields from the same model.
- A configured active child upload source with an `aggregate_parent_field`.
- A configured active parent upload source with stored computed totals depending
  on child rows.
- A model that is not configured as an upload source.
- A sync-internal model named with `ab.odoo.sync.` or `ab_odoo_sync`.
- A stored computed field with `compute_sudo=True`.
- A non-stored computed field.
- A stored regular field.
- A readonly/log-access-only write path touching only `create_uid`,
  `create_date`, `write_uid`, or `write_date`.

## Add-To-Compute Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| ATC-01 | Active upload source scheduled for stored compute | Write a dependency field that schedules a stored computed field on the same record | One pending upsert is collected for the source record |
| ATC-02 | Multiple stored computed fields scheduled for same record | Write one dependency that schedules two stored computed fields | One final upsert is emitted, not one per field |
| ATC-03 | Same stored computed field scheduled repeatedly | Write dependencies multiple times before precommit | One final upsert is emitted |
| ATC-04 | Recordset contains multiple records | Batch-write dependencies on several records | One upsert per real source record |
| ATC-05 | Recordset contains duplicates | Schedule recompute with duplicate record ids in the recordset | One upsert per unique `(model, id)` |
| ATC-06 | Non-stored computed field scheduled | Trigger a non-stored compute | No upload snapshot is collected |
| ATC-07 | Stored non-computed field passed to hook | Call/simulate `add_to_compute` with a stored field that has no compute method | No upload snapshot is collected |
| ATC-08 | Field model not in registry/environment | Simulate stale or missing `field.model_name` | No crash; no snapshot |
| ATC-09 | Model is not an active upload source | Trigger stored recompute on an unconfigured model | No snapshot |
| ATC-10 | Upload source is inactive | Trigger stored recompute on a configured but inactive source | No snapshot |
| ATC-11 | Upload source is forbidden by sync rules | Trigger stored recompute on a forbidden model | No snapshot |
| ATC-12 | Sync-internal model recompute | Trigger stored recompute on `ab.odoo.sync.*` or `ab_odoo_sync*` | No snapshot |
| ATC-13 | Excluded core model recompute | Trigger stored recompute on `ir.model.data` or `ir.module.module` | No snapshot |
| ATC-14 | Context skip flag | Trigger stored recompute with `skip_ab_odoo_sync_upload=True` | No snapshot |
| ATC-15 | Unsaved virtual/new records | Schedule recompute for records with non-integer or non-positive ids | No snapshot |
| ATC-16 | Inactive business record | Trigger stored recompute on an inactive source record | Snapshot is emitted because collector uses `active_test=False` |
| ATC-17 | Compute-sudo field | Trigger stored recompute for `compute_sudo=True` field as a restricted user | Snapshot is emitted through sudo serialization without access errors |
| ATC-18 | Add-to-compute followed by direct write | Schedule recompute and write a normal stored field on the same record | One final upsert is emitted with both changes |
| ATC-19 | Add-to-compute followed by unlink before precommit | Schedule recompute, then unlink the same source record | Archive wins; no stale upsert for the deleted record |
| ATC-20 | Add-to-compute for archived snapshot key | A prepared archive exists for the same `(model, id)` | Upsert key is removed/ignored so archive is emitted once |

## Low-Level Write Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| LWW-01 | Stored compute flush writes actual value | Trigger recompute and flush the stored field through `_write_multi` | One upsert is collected even if `add_to_compute` was missed |
| LWW-02 | Manual stored field write | Write a normal stored field on an upload source | One pending upsert is collected through normal write and/or `_write_multi` |
| LWW-03 | Write only log-access fields | Force a low-level write with only `write_uid`/`write_date` | No snapshot from `_write_multi` |
| LWW-04 | Write only non-stored fields | Write values that do not map to stored fields | No low-level snapshot |
| LWW-05 | Mixed stored and log-access fields | Write one real stored field plus log-access fields | Snapshot is collected |
| LWW-06 | Empty `vals_list` | Call/simulate `_write_multi` with no meaningful values | No snapshot and no crash |
| LWW-07 | Batch `_write_multi` with different vals per record | Recompute/write different stored fields across a recordset | One upsert per record in `self` |
| LWW-08 | `_write_multi` on non-upload model | Flush stored fields on an unconfigured model | No snapshot |
| LWW-09 | `_write_multi` with context skip | Flush with `skip_ab_odoo_sync_upload=True` | No snapshot |
| LWW-10 | `_write_multi` during collector emission | Outbox creation writes audit fields while `emitting=True` | No recursive upload snapshots |
| LWW-11 | `_write_multi` failure before persistence | Force `_ORIGINAL_WRITE_MULTI` to raise | No snapshot emitted for failed write |
| LWW-12 | `_write_multi` succeeds but snapshot marking fails | Mock source lookup/capture failure after write | Exception is logged and raised; transaction rolls back |

## Collector And Precommit Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| COL-01 | One transaction, many hooks | Create, write, recompute, and flush the same record before commit | One final upsert event |
| COL-02 | Final-state serialization | Write value A, then value B before precommit | Snapshot payload contains value B |
| COL-03 | Multiple models in collector | Change records from two upload source models | Upserts are grouped by model and emitted for all existing records |
| COL-04 | Record deleted before precommit | Collect an upsert key, then unlink the record | Existing check prevents an upsert for the missing record |
| COL-05 | Archive and upsert in same transaction | Modify and unlink the same record | Archive snapshot is emitted once; no upsert |
| COL-06 | Archive ordering for cascades | Delete a parent with cascading upload-source children | Child archives are prepared/emitted before parent archive |
| COL-07 | Set-null dependency survivor | Delete parent where child upload source has `ondelete='set null'` | Surviving child gets an upsert after unlink |
| COL-08 | Collector precommit scheduled once | Mark many records repeatedly | Only one precommit callback is registered per transaction collector |
| COL-09 | Empty collector flush | Invoke flush with no state or already-emitting state | No operation and no crash |
| COL-10 | Rollback before precommit | Change source record then rollback transaction/savepoint | No outbox event persists |
| COL-11 | Savepoint rollback after collection | Collect inside savepoint and roll back to savepoint | No stale event should persist for rolled-back changes |
| COL-12 | Savepoint success then outer commit | Collect inside a successful savepoint | One final event persists after outer commit |
| COL-13 | Precommit failure | Force serialization/outbox failure during collector flush | Commit fails; no partial successful business commit is accepted |
| COL-14 | Collector state reset between transactions | Commit transaction A, then transaction B changes same record | Separate outbox events are emitted per committed transaction |
| COL-15 | Active-test behavior | Collect inactive record and commit | Snapshot is created because flush browses with `active_test=False` |
| COL-16 | Missing model during flush | Remove/uninstall model between collection and flush in a controlled test | No crash; skipped if model is not in `env` |
| COL-17 | Emitting guard | Snapshot capture writes outbox and updates `source_revision` | No nested collector entries for outbox writes |
| COL-18 | Deferred sender context | Capture with `defer_ab_odoo_sync_upload_sender` when available in test context | Outbox rows are created without immediately queueing sender jobs |

## Create, Write, Unlink Interaction Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| CWU-01 | Create source record with stored computed fields | Create record with dependencies that cause stored compute | One upsert with final stored compute values |
| CWU-02 | Create then update before commit | Create source record and update a dependency in same transaction | One upsert with final values |
| CWU-03 | Write source record updates aggregate parent | Write child source with configured parent field | Child and parent each receive one final upsert |
| CWU-04 | Stored compute on child updates aggregate parent | Change child dependency that recomputes child field | Child is captured; parent is captured only if aggregate parent logic is triggered by write/create/unlink path |
| CWU-05 | Parent stored compute from child one2many changes | Add, update, or remove child rows affecting parent stored total | Parent final upsert is emitted through `add_to_compute` or `_write_multi` |
| CWU-06 | Unlink source record | Delete an upload source record | Prepared archive snapshot is emitted after unlink |
| CWU-07 | Unlink after prior writes | Write source record then unlink it in same transaction | Archive only, using pre-unlink payload |
| CWU-08 | Unlink non-source parent of source children | Delete non-source parent that cascades to source children | Relevant source child archives are emitted |
| CWU-09 | Restrict dependency unlink | Attempt delete blocked by `ondelete='restrict'` | No archive/upsert events persist because transaction fails |
| CWU-10 | Empty recordsets | Call create/write/unlink paths where recordset is empty | No snapshot and no crash |

## Deduplication And Ordering Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| DED-01 | Create hook plus `_write_multi` hook for same record | Create source record where computed field flush writes stored values | One upsert event |
| DED-02 | Write hook plus add-to-compute for same record | Write dependency on source record | One upsert event |
| DED-03 | Parent captured from child writes multiple times | Batch update many children with same parent | One parent upsert event |
| DED-04 | Archive prepared more than once | Multiple unlink dependency paths find same source record | One archive event, preserving deterministic archive order |
| DED-05 | Upsert key then archive snapshot | Record marked for upsert and later archived | Archive snapshot removes pending upsert |
| DED-06 | Archive snapshot then upsert key | Archive snapshot exists and a late recompute/write hook tries to mark upsert | Upsert is not added |
| DED-07 | Deterministic multi-model order | Collect records across models with unordered input ids | Flush order is stable by sorted model names and archive order |

## Transaction And Concurrency Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| TXN-01 | Two concurrent transactions update same record | Commit transaction A and B in different orders | Each committed transaction creates its own event with that transaction's final state |
| TXN-02 | Concurrent rollback | One transaction rolls back after collection while another commits | Only committed transaction creates events |
| TXN-03 | Long transaction with many writes | Repeated dependency writes before one commit | One event per final source record, no unbounded duplicate collector growth |
| TXN-04 | Flush before commit, then more writes | Force flush/recompute mid-transaction, then update again | Final precommit snapshot reflects latest committed state |
| TXN-05 | Nested recomputes | Compute method writes dependency that schedules another stored compute | Final record is captured once after all recomputes settle |
| TXN-06 | Exception inside compute method | Dependency write triggers compute that raises | No outbox event persists |
| TXN-07 | Manual `env.cr.commit()` in controlled test | Commit without normal HTTP/job boundary | Precommit collector still flushes |

## Source Configuration Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| SRC-01 | Activate source then write model | Toggle source active and write a record | Capture follows the active source state after cache invalidation/clear |
| SRC-02 | Deactivate source then write model | Toggle source inactive and write a record | No new capture after source cache is cleared |
| SRC-03 | Invalid model source rejected | Configure source for missing model | Validation error |
| SRC-04 | Forbidden model source rejected | Configure source for forbidden sync-rule model | Validation error |
| SRC-05 | Invalid aggregate parent field rejected | Configure non-Many2one aggregate field | Validation error |
| SRC-06 | Missing aggregate parent value | Write child with configured parent field empty | Child captured; no parent capture |
| SRC-07 | Aggregate parent inactive | Write child whose parent is inactive | Parent capture uses `.exists()` and should capture inactive parent if source model is active |

## Serialization And Payload Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| PAY-01 | Stored computed value included | Trigger stored compute and commit | Payload contains computed field's final stored value |
| PAY-02 | Non-stored computed value excluded | Trigger non-stored compute | Payload does not rely on non-stored transient value |
| PAY-03 | False/null computed value | Compute sets `False`, `0`, empty string, or empty relation | Payload preserves the actual falsy value |
| PAY-04 | Many2one computed value changes | Compute changes a stored Many2one | Payload serializes the final related id/value per service contract |
| PAY-05 | Monetary/float precision | Compute changes float/monetary stored values | Payload preserves expected Odoo precision |
| PAY-06 | Datetime/date compute | Compute changes date/datetime stored value | Payload uses expected UTC/server serialization |
| PAY-07 | Binary/html/text compute | Compute changes large stored payload | Snapshot succeeds or fails with a clear bounded error depending on serializer support |
| PAY-08 | Serialization after sudo | Restricted user triggers change | Payload serialization succeeds with sudo while still using correct source record data |
| PAY-09 | Source write date | Upsert event stores source `write_date` from final record state | `source_write_date` is not older than the final business write |
| PAY-10 | Archive source write date | Archive prepared before unlink | Archive snapshot contains the pre-unlink source `write_date` or fallback timestamp |

## Negative And Safety Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| SAF-01 | Inventory computed/system quantities | Ensure tests never directly assign protected stock quantities | Inventory changes use approved business flows only |
| SAF-02 | External database safety | Run upload capture tests without external DB writes | No B-Connect/E-Plus tables are modified |
| SAF-03 | Outbox unlink blocked | Try to delete upload outbox event | UserError is raised |
| SAF-04 | Outbox status maintenance | Mark pending/failed outbox as Not Sync | Upload hooks do not capture outbox model changes |
| SAF-05 | Queue sender failure | Force upload queue enqueue failure during capture | Business transaction fails or error handling matches service contract; no silent partial state |
| SAF-06 | Access-limited user | Restricted user writes allowed source record | Capture succeeds without branch/data leakage in payload |
| SAF-07 | Multi-company or branch context | User from one branch changes branch-scoped source record | Payload contains only the changed source record and no unrelated branch records |

## Performance And Regression Coverage

| ID | Edge case | Action | Expected result |
| --- | --- | --- | --- |
| PERF-01 | Large batch write | Update hundreds or thousands of source records | One outbox per record; query count remains bounded enough for job/runtime limits |
| PERF-02 | Large recompute fan-out | One dependency change schedules many stored recomputes | Collector memory grows by unique keys, not duplicate hook invocations |
| PERF-03 | Large unlink cascade | Delete parent with many dependent children in a controlled fixture | Archive planning remains deterministic and avoids per-record dependency discovery |
| PERF-04 | Registry dependency index reuse | Call unlink planning repeatedly | Dependency index is cached on registry and not rebuilt each time |
| PERF-05 | Upload source cache behavior | Repeated writes to same model | Source active lookup uses cache and does not query source config per hook beyond expected invalidation |

## Minimum Acceptance Criteria

- Stored computed field recomputes create upload events for active upload source
  records even when no explicit write hook sees the dependency relationship.
- The low-level `_write_multi` safety net captures stored writes that bypass
  normal semantic scheduling.
- One committed transaction creates at most one upsert event per source record
  and one archive event per deleted source record.
- Upsert events serialize the final state visible at precommit time.
- Archive events serialize the pre-unlink state and suppress stale upserts for
  the same record.
- Context skip, sync-internal models, forbidden models, inactive sources,
  non-stored fields, virtual records, failed writes, and rollbacks do not create
  events.
- Collector emission does not recursively capture outbox/source model writes.
- Multi-record, aggregate-parent, cascade, set-null, inactive-record,
  restricted-user, and concurrent-transaction paths are covered.
