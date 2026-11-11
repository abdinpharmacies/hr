Current changes before commit:

- Fix Connect to Central and Sync Now failing with an unexpected positional argument from Operations list buttons.
- Use record-method RPC dispatch for empty, single and multiple selections; preserve administrator checks and existing synchronization behavior.
- Remove the unused api import and document the button calling contract.

Files changed:

- ab_branch_sync/models/enrollment.py
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-11-button-rpc.md

Verification:

- Four focused tests passed using the installed Odoo 19 call_kw dispatcher with mocked method lookup, database services and network operations: successful empty/single/multiple selections, denied non-administrator access, missing authorization, and reproduction with the old decorators.
- Test script: /tmp/test_branch_sync_button_rpc.py (development only).
- No user-facing source strings changed; existing Arabic catalogs retained.
- No database upgrade, live synchronization, or server restart performed. Python code must be reloaded by the running branch server.

Recent relevant commit:

- Commit: bea50b07bf7ddd48c6dd9d029149d1c4756d566e
- Author: hager yasser
- Date: 2026-11-10
- Original subject: refactor(ab_branch_sync): decouple branch synchronization from replication
- User-facing change: run Branch Synchronization independently of master-data replication.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/replication.py (removed)
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-10-replication-independence.md
