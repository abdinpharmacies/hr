# ab_branch_sync

Version 19.0.5.1.0. Branch inventory client with offline stock cache and immediate bill retry.

See [workflow.md](workflow.md) for setup, unit mapping, inventory ownership, POS behavior and recovery.

Configure `ab_central_branch_connection.url`, `ab_central_branch_connection.database`, and
`ab_central_branch_connection.api_key` in Settings → Technical → Parameters → System Parameters
(developer mode). Administrators connect and synchronize from the buttons above
Branch Synchronization → Operations. Reconnect after changing connection parameters.

All nine connection, authorization, readiness, store-scope, status and POS interval
parameters use the `ab_central_branch_connection.*` namespace. See the workflow
for existing-installation key renaming and reconnection instructions.
