# Central synchronization

Approved new-model exception: `ab_central_sync_operation` is the only new model.
It stores immutable JSON operations and transport results. It does not replace
sales documents, stock movements, allocations, payments, or employee sessions.
There is no dependency on `ab_branch_api`, and callcenter API contracts and its
operation journal are untouched.

## Activation

Install the same module version on branch and central. The default role is
disabled. Configure system parameters as an administrator:

| Parameter | Branch | Central |
| --- | --- | --- |
| `ab_central_sync.role` | `branch` | `central` |
| `ab_central_sync.url` | HTTPS central base URL | unused |
| `ab_central_sync.database` | central database name | unused |
| `ab_central_sync.api_key` | origin credential | unused |
| `ab_central_sync.peers` | unused | JSON object described below |

The central `peers` object is keyed by the branch's existing `database.uuid`.
Each entry contains `api_key`, `stores` (allowed E-Plus store serials),
`replica_serial` (existing origin replica DB serial), and `actors`.
Each actor key is the branch user's login, with a value containing `login`
(the mapped central user) and `employees` (allowed stable employee references).
Example structure with placeholders, not usable credentials:

```json
{
  "BRANCH-DATABASE-UUID": {
    "api_key": "REPLACE-PRIVATELY",
    "stores": [101],
    "replica_serial": 101,
    "actors": {
      "branch-login": {
        "login": "central-login",
        "employees": [{"accid": "EMPLOYEE-CODE"}]
      }
    }
  }
}
```

The employee reference must match the reference emitted by the branch: first
nonempty `eplus_serial`, otherwise `code`, then employee `accid`, otherwise a shared external XML ID.
No database-local IDs are accepted as master references. API keys are secrets;
configure them privately and never put real values in source control.

Central validates origin/store/actor delegation and the employee's current
central profile. It creates a short-lived existing POS session for that delegated
employee, invokes normal business actions under the mapped user, and closes the
session. It does not require an employee to leave an interactive session open,
grant groups, or bypass native permission checks.

Prerequisites: native inventory enabled for participating stores on both sides;
matching product, unit, source-batch, employee, contract and promotion identities;
aligned opening stock; configured source replica and authorized employee
profiles. Sources need a shared unambiguous reference (shared XML IDs may be used
when no stable code exists). Ordinary branch-local source IDs are not portable.
Legacy E-Plus posting is not synchronized by this module. Do not activate this
module as a substitute for converting and reconciling a legacy store.

The module captures new native sale approvals, cashier settlements, return
approvals, refund settlements, and pending-sale cancellations. Historical sales
are not imported. Returns requiring a historical original remain review work.

## Delivery and recovery

Local business changes and outgoing JSON commit together. A post-commit callback
attempts delivery using a fresh cursor. A 15-minute cron retries durable queued
or uncertain operations. Disabling the role retains the journal.

Central routes: POST `/ab_central_sync/v1/submit`, `/status`, `/reconcile`.
Requests use `Authorization: Bearer ...` and `X-Odoo-Database`. The database must
also pass Odoo's host database filter. Only HTTPS is used by the sender. Redirects
are refused. Requests are limited to 2 MB.

Each origin/store stream uses a transactional no-gap serial. Central accepts in
serial order; an unresolved operation blocks its later dependents. Identical
replays return the previous result; changed content is rejected. The incoming
result and all business effects commit atomically. Stock allocation, unit price,
cost and agreed totals must match; differences roll back the central business
transaction and remain visible in the journal.

Managers can inspect payloads/errors and retry rejected incoming operations
once configuration or master-data issues are fixed. Also retry the corresponding
outgoing rejected operation so delivery resumes. Neither action changes its
payload. Accepted operations cannot be retried or edited. Corrections need an
existing business reversal/new operation. Archived operations still participate
in identity and ordering checks.

“Check Missing Serials” checks a bounded window of up to 1,000 serials beginning
at the selected outgoing operation, against the branch's committed high-water
mark. Missing/failed serials and the window end appear in Reconciliation. Select
a later operation to inspect another window.

No central configuration, production data, external databases, or existing
callcenter code is changed by installation. Enable one verified branch first.
