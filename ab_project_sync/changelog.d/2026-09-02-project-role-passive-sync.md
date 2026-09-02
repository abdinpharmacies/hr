# Project Role Passive Sync Metadata

## Recent relevant commit

- Commit: none
- Author: n/a
- Date: n/a
- Subject: new module
- This module has no previous committed history in the repository.

Files changed:

- none

## Current changes before commit

- Add a focused custom addon that inherits `project.role` without editing Odoo core.
- Add passive sync identity fields `db_serial`, `rec_id`, and `payload_json`.
- Add a unique `(db_serial, rec_id)` constraint so same-name passive auto-mapping can validate the target model.
- Relax the standard required `name` field for passive placeholder compatibility.
- Add Arabic translations for the new field and constraint labels.

Files changed:

- `ab_project_sync/__init__.py`
- `ab_project_sync/__manifest__.py`
- `ab_project_sync/models/__init__.py`
- `ab_project_sync/models/project_role.py`
- `ab_project_sync/i18n/ar.po`
- `ab_project_sync/i18n/ar_001.po`
- `ab_project_sync/changelog.d/2026-09-02-project-role-passive-sync.md`
