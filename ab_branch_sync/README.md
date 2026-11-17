# ab_branch_sync

Version 19.0.5.1.2. Branch inventory client with offline stock cache and immediate bill retry.

See [workflow.md](workflow.md) for setup, unit mapping, inventory ownership, POS behavior and recovery.

Configure `ab_central_branch_connection.url`, `ab_central_branch_connection.database`, and
`ab_central_branch_connection.api_key` in Settings → Technical → Parameters → System Parameters
(developer mode). Selecting the branch in the POS automatically attempts the
central connection and initial stock download before stock is loaded. Administrators
can also connect and synchronize from Branch Synchronization → Operations.
Changing connection parameters requires successful preparation again.

All nine connection, authorization, readiness, store-scope, status and POS interval
parameters use the `ab_central_branch_connection.*` namespace. See the workflow
for existing-installation key renaming and reconnection instructions.
