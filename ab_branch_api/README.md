# Branch API

Native Odoo bearer API keys authenticate all eight version 1 methods. Each
request supplies `db_serial`, matching the configured active replica, whose
local default sales store scopes the operation. Active internal non-admin users
use their existing business permissions; there are no API roles or bindings.

See [the connection guide](../ab_sales/doc/CALLCENTER_BRANCH_CONNECTION.md) for
provisioning, permissions, request contracts, identity mapping, and rollout.
