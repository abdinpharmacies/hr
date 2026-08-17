## 614d18f551a72003422b9420a1eb0b1ff0c9f8b0

- Author: emadco88 <emadco88@gmail.com>
- Date: Wed Aug 12 15:31:16 2026 +0300
- Subject: ab_odoo_sync/ REFACTORING

User-facing changes:

- Replaced free-text branch checkpoint identity with configured `db_serial`.
- Added branch-side sync event states for pending, full sync, partial sync, failed, and manually skipped events.
- Recorded missing branch fields as partial sync details instead of silently ignoring them.
- Added admin actions to mark failed or pending events as Not Sync and to manually clean consumed events.
- Disabled automatic event cleanup and kept cleanup bounded by active `db_serial` checkpoints.
- Added Arabic translations for the new Odoo Sync labels and notifications.

Files changed:

- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_checkpoint.py`
- `ab_odoo_sync/models/ab_odoo_sync_event_state.py`
- `ab_odoo_sync/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`

## 3db5d596c9429ff082c3fe9b0466692b945f788f

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Jul 28 15:21:42 2026 +0300
- Subject: INIT commit pos19

User-facing changes:

- Added the Odoo Sync addon for event-driven one-way synchronization from MAIN to BRANCH servers.
- Added sync configuration, event log, checkpoint views, HTTP endpoints, and scheduled branch pull behavior.

Files changed:

- `ab_odoo_sync/__init__.py`
- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/controllers/__init__.py`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_checkpoint.py`
- `ab_odoo_sync/models/ab_odoo_sync_config.py`
- `ab_odoo_sync/models/ab_odoo_sync_event.py`
- `ab_odoo_sync/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`

## e148a306a03fb4f91e961bb06cac72adb6a6e62b

- Author: emadco88 <emadco88@gmail.com>
- Date: Thu Aug 13 08:52:48 2026 +0300
- Subject: ab_odoo_sync/ UPD Two-way sync

User-facing changes:

- Added a branch-to-MAIN JSON upload endpoint that stores incoming rows before queueing target apply work.
- Added upload record audit/status tracking with Queue Apply, Replay Failed, and Mark Not Sync admin actions.
- Applied queued rows to `<source_model>__sync` target models by `(db_serial, rec_id)` while preserving failed payloads for replay.
- Added `queue_job` registration for upload apply jobs and a hard manifest dependency on `queue_job`.
- Fixed the module cron XML for Odoo 19 by removing invalid `ir.cron` fields.
- Added Arabic translations for upload sync labels, validation messages, and notifications.

Files changed:

- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`

## 0a7437e39da4805df7cf50de1b00de5c66df2c02

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Thu Aug 13 13:53:32 2026 +0300
- Subject: ab_odoo_sync/Fix: Replaces the conflicting queue_job dependancy with the already existing integration_queue_job provider in manifest

User-facing changes:

- Fixed installation on databases that already use Integration Queue Job by registering upload work with the existing queue provider instead of installing a conflicting second provider.
- Made clean installations keep branch pulling disabled until synchronization settings are configured.
- Made an active but unconfigured branch pull skip safely with a clear translated reason instead of failing every minute.
- Added system-only access for the synchronization service model.
- Updated developer metadata while preserving company ownership.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/security/ir.model.access.csv`

## 7b027d7f419e525251e14a4eb8e4c478e9b1c64f

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Sun Aug 16 12:23:08 2026 +0300
- Subject: ab_odoo_sync/Feat: Simulation the main server and branch sync and test connection, sending data

User-facing changes:

- Fixed authenticated HTTP endpoints on Odoo 19 by using the supported JSON request API.
- Added explicit MAIN database selection so a branch can connect to the correct database on a multi-database server.
- Added an authenticated health endpoint and a branch-side connection test covering health, pull, and an empty push without touching business records.
- Added an explicit branch upload method for approved callers while keeping automatic business export disabled.
- Required MAIN-side active checkpoint registration for every connecting `db_serial`.
- Prevented checkpoint acknowledgements from moving backward or beyond the latest known MAIN event.
- Added English and Arabic connection messages, a Test Branch Connection menu action, and a module version bump.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`

## Current changes before commit

User-facing changes:

- Refresh the active Odoo Sync list or form immediately after manual status-changing actions.
- Keep the existing toast messages for upload outbox sending, upload record apply/replay/skip, event skip, apply profile actions, checkpoint cleanup, and branch connection tests while chaining the standard Odoo reload client action.

Files changed:

- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/models/ab_odoo_sync_checkpoint.py`
- `ab_odoo_sync/models/ab_odoo_sync_event_state.py`
- `ab_odoo_sync/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/models/ab_odoo_sync_upload_record.py`
