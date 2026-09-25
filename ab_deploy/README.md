# Deployment Manager

## Manually resolve a failed server

Open the failed record under **Execution Jobs** and choose **Mark as Manually Resolved**.
Executors and Deployment Administrators can confirm an external fix with a required
resolution note. The request must remain approved and no active queue run may handle
that execution. This is a human confirmation: Odoo does not run SSH checks or commands.

The job and target show **Manually Resolved** (تمت المعالجة يدويًا), separately from
Succeeded. The resolver, resolution time and note are readonly. The original exit code,
error, failure category, timestamps, logs and attempts are retained. This terminal state
is excluded from selection, failure retry, monitoring and recovery; late worker observations
cannot overwrite it. The original queue run outcome is not rewritten.

A Deployment Administrator can choose **Undo Manual Resolution**, supplying a reason.
This restores Failed without scheduling a retry. Resolution details remain visible, and
both transitions, actors, timestamps and reasons are retained in Deployment Audit Logs.
A later resolution updates the displayed latest resolution while preserving the audit.

The existing **Resolve Execution** action for Unknown executions remains separate: it
checks remote status and is not a declaration that a failed server was manually fixed.

Lists order Failed, Unfinished, Cancelled, Delayed, Manually Resolved, Succeeded. With
ab_deploy_telegram installed, summaries count manually resolved servers separately and
Arabic Markdown files use the same ordering. Resolve/undo does not send a notification;
use **Send Deployment Report** to publish the current result when desired.

## Required post-deployment checks

In Command Catalog, administrators create **Post-deployment Check** commands first,
then link one or more under **Required Checks** on every **Deployment Action**.
**Check Sequence** controls their order (record ID breaks ties). Referenced checks
cannot be archived or converted into actions while an active action requires them.
Existing unconfigured actions remain in the catalog, but must be configured before
editing or submitting them for a new approval. Inactive actions may be archived.

Saving an action line automatically adds read-only linked check rows immediately
after it. Edit **Sequence** on manual action rows to reorder whole blocks. Shared
checks run after each action that requires them. Manual standalone checks run last;
check-only requests are allowed. Removing or replacing an action removes its generated
checks. Duplication copies manual lines and regenerates their checks.

Use **Refresh Linked Checks** in a draft after catalog changes; opening a request does
not modify its rows. Submission also refreshes and validates the complete blocks.
Command names, scripts, types, links and execution order are frozen in each target
snapshot with check policy version 2. Approval validates the frozen blocks rather than
later catalog edits. Existing version 1 and pre-policy submissions, later batches and
retries keep their frozen scripts. Resubmitting a draft applies the current policy.

Print diagnostic output and exit 0 for success, 1 for a detected issue, or 2 when a check
cannot complete reliably. All nonzero exit codes fail that server and stop later commands;
these conventions do not add an output parser or separate failure states. A failing action
skips checks. Every action and check must pass for the server to succeed. Other servers
keep independent results. Earlier changes are not rolled back.

Checks should observe rather than modify the server; arbitrary Bash cannot be proven
read-only automatically. Use noninteractive tools and explicit result validation. For
example, a successful SQL query does not imply no issue: inspect its returned rows and
exit nonzero when unwanted rows exist.

New scripts record START/END markers containing command number, type, name and exit code.
Command output remains in the existing execution logs. Markers do not print script bodies.
Each command executes in its own fail-fast Bash process, starting in the SSH user's home.

## Retry selected failures

Executors can select SSH or script failures and click **Retry Selected Failures**.
**Select All Failures** selects eligible failures, while **Retry Failure** is available
on individual executions. Setup failures, successful/cancelled/manually resolved jobs,
and superseded executions are not eligible. Delayed servers still use **Queue Selected
Servers**; mixed selections containing ineligible servers are rejected.

A confirmed script failure (including a failed post-deployment check) creates a fresh
execution linked by **Retry Of**. It runs the entire frozen approved script and checks
from the beginning with a new remote key, log offsets and capture times. Previous
execution results and logs remain available. The target and reports show the latest
execution, counting the server once. No new approval is required. If updates were not
pushed earlier, push them first; the approved script must already pull the branch.

SSH retries retain the existing reconnect/reconcile behavior when a launch may have
occurred. Unknown monitoring status uses **Resume Monitoring**. Active queue handlers
prevent duplicate retries, and existing per-server scheduling and remote locking
prevent simultaneous deployment commands. Existing retry method names remain callable
as compatibility wrappers. No commands are run automatically by the module upgrade.

## Per-server command parameters

Administrators configure **Server Parameters** in **Config → Command Catalog**.
Each row supplies Server, Variable Name and Value for that command. Use names such
as ``DEPLOY_MODULES`` and reference them as ``"${DEPLOY_MODULES}"`` in Bash. A variable
can appear only once per command/server. Names must match ``DEPLOY_[A-Z][A-Z0-9_]*``.

Automatic variables use existing server fields; they cannot be overridden by rows:

| Variable | Server value |
| --- | --- |
| ``DEPLOY_DATABASE`` | Database Name (default ``abdin_replica19``) |
| ``DEPLOY_PYTHON`` | Odoo Python Venv |
| ``DEPLOY_CONFIG`` | Odoo Server Config |
| ``DEPLOY_SERVER_PATH`` | Odoo Server Path |
| ``DEPLOY_LOG_PATH`` | Odoo Log Path |
| ``DEPLOY_ODOO_BIN`` | Odoo Server Path plus ``/server/odoo-bin`` |

Example (configure ``DEPLOY_MODULES`` for each target on this command)::

    sudo -n -u odoo19 "${DEPLOY_PYTHON}" "${DEPLOY_ODOO_BIN}" \
      -d "${DEPLOY_DATABASE}" -u "${DEPLOY_MODULES}" \
      --config "${DEPLOY_CONFIG}" --no-http --stop-after-init


At submission, a private lookup resolves only the selected command/server rows.
Referenced values become shell-quoted assignments inside each command's separate
Bash process. Values are data, not executable substitutions; keep references quoted
and do not pass them through ``eval``. Assignments are local shell variables, not
implicitly exported to child processes. Action and check commands have independent
parameter rows. Missing or empty referenced values block submission, including
references found in comments/literal text. Reserve ``DEPLOY_`` names for injected values;
use other names for local variables. This is not a Jinja or Python expression engine.

Resolved scripts are frozen for approval and retries. Catalog or server changes
apply only to a later submission. Existing frozen scripts remain unchanged.
Only Deployment Administrators can read or manage parameter records, including via
RPC/export, but resolved ordinary values are visible in scripts and audit history.
**Do not store credentials or secret tokens in this version.**

## Request privacy and assigned execution

Owners see their own requests. The chosen approver and executor can see assigned
requests only while holding their corresponding roles. Deployment Administrators
retain access within existing company restrictions. These rules also apply to
request commands, targets, execution history, attempts, logs, messages and attachments.
Deployment attachment download tokens/public flags do not bypass request access.
Former followers/recipients are excluded from future request notifications when they
lose access. Existing configured Telegram group audiences remain unchanged.

The developer submits to an approver. In Requested state the approver must choose an
active **Assigned Executor** who already has the Executor role before approving.
This does not grant any role automatically. A developer can also execute when assigned
and already holding that role; self-approval remains prohibited. Only owners or
administrators edit draft contents, withdraw or cancel requests. Approvers may enter
decision notes on assigned requested deployments.

Only the assigned executor or a Deployment Administrator may select targets, test
SSH, queue, retry, resume or manually resolve an execution. Undo resolution remains
administrator-only. After approval, only administrators can reassign, and only after
active executions/queue runs finish. Existing approvals/scripts are retained; an
administrator must assign an executor on older approved requests before new executor
actions. Running work is not interrupted by this upgrade.

Queue Runs and execution logs remain visible with their request. Generic Audit Logs
and raw deployment queue records are administrator-only. Inaccessible competing
requests show a generic conflict notice: users can wait without seeing hidden details
or cancelling another executor's work. Shared Servers and Command Catalog retain
existing access. Configuration parameters remain administrator-only.
