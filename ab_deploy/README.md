# Deployment Manager

## Cancel waiting deployments and resolve blockers

**Cancel Older Waiting Executions and Queue** cancels only waiting executions on
the selected servers. A persistent notification lists remaining visible blockers;
restricted deployments receive a generic notice. Running executions must finish.

For an Unknown execution, a Deployment Administrator can choose **Check and Resolve**
from the conflict list or the request's Execution Jobs list. Inspect the server and
enter an inspection note. Confirmation checks SSH again and refuses while the
execution's tmux session is alive. Missing completion evidence with no live session
records Failed; connection or malformed-response errors leave the job unchanged.

Resolution from the conflict screen returns to refreshed conflicts and preserves
the selected targets. Confirm queuing separately. Already queued deployments with
an active queue run can proceed once their blockers are resolved; use **Resume
Monitoring** if there is no active run. Resolution never replays the old script.

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

## Request dependencies

Set **Depends On** on a draft request Y to require an earlier request X. The
dependency becomes read-only with the approved request. Self-dependencies and
cycles are rejected; chains such as Z depending on Y depending on X are supported.

Dependencies are checked per server using the latest execution in X.
**Succeeded** or **Manually Resolved** allows that server to queue in Y.
Failed, Delayed, Queued, Running, Unknown and Cancelled all block it. A server missing from X
also blocks it. Success or manual resolution on another server does not satisfy
the dependency. A newer failed attempt overrides an older resolved attempt.
Undoing manual resolution blocks dependent executions that have not started;
already running executions continue monitoring.

Blocked servers can still be selected. **Queue Selected Servers** reports all
blocked servers and rejects the entire selection without creating jobs or clearing
selection. Deselect blocked servers to queue a ready subset. After X succeeds or is manually resolved,
queue Y manually; there is no automatic submission. **Retry Selected Failures**
and individual retry actions enforce the same dependency. Existing queue conflict
choices cannot bypass it. Restricted prerequisite details are omitted from errors.

The runner checks again before launching a queued execution. If its prerequisite
is no longer satisfied, the execution stays Queued with an explanatory error and
is skipped for that run. After correcting the prerequisite, use **Resume Monitoring**.
Monitoring and log collection for already-started executions continue normally.
Requests without a dependency retain the existing workflow.

## Update approved scripts

A Deployment Administrator edits commands in the catalog, then opens or refreshes
an approved request. The red **Update Commands** button appears when Delayed or Failed servers
have changes in their commands, required checks or resolved parameters. The
button also appears for rendering errors so the administrator can inspect them.
Form reads do not change deployment records or lock executions.

**Update Commands** opens a ready-made diff and complete before/after scripts for
all changed Delayed/Failed servers. Unchanged servers are skipped automatically.
Enter the required reason and click **Confirm Update**: the scripts are approved
and applied immediately, including on the administrator's own request. There is
no separate approval, pending revision or approval activity. The initial request
approval workflow remains unchanged. Developers and executors cannot use this
administrator action.

The confirmation rechecks catalog content, affected servers and execution
snapshots under locks. If anything changed after preview, reopen Update Commands
to review the current scripts. Targets with active queue runs cannot be updated.
Queued, Running, Unknown, Succeeded, Cancelled and Manually Resolved targets remain
outside this workflow. Changing command selection/order or command types still
requires a new request. Connection, timeout and log-capture settings are preserved.

Confirmation records one internal chatter note, **Commands updated and approved**,
with the administrator, reason, affected servers, changed commands and a link to
the immutable revision. Full scripts remain in the access-controlled revision
history. Previous execution scripts, settings, keys and logs are retained; existing
jobs without their own snapshots are preserved before their target is updated.
No migration hook or broad history rewrite is used.

Queueing and retrying affected servers are blocked until an administrator confirms
Update Commands. Selection remains available. The worker checks again before
launch: if commands changed while a job was queued, it fails that unlaunched job
with an update-required error. After its queue run finishes, update the commands
and retry. Already running executions continue monitoring their original script.

Queue or retry manually after confirmation. Revised retries use a fresh execution
and key, including SSH or setup failures, and run the script from the beginning;
the corrected script must handle steps already completed. Historical monitoring
continues with the original execution snapshot. Revisions stay on the original
request, so corrected success in X satisfies Y's dependency on X for that server.

Previously approved/rejected/cancelled revisions remain readable. If an old pending
revision exists, an administrator must explicitly cancel it from Script Revisions
before preparing a new update. Old pending proposals are never approved silently.

## Retry selected failures

Executors can select SSH or script failures and click **Retry Selected Failures**.
**Select All Failures** selects eligible failures, while **Retry Failure** is available
on individual executions. Setup failures without an approved script revision, successful/cancelled/manually resolved jobs,
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

Administrators configure the **Server Parameters** tab in **Config → Command Catalog**.
The **Bash Script** tab contains the script editor; parameter notes, bulk controls,
shared defaults, and server overrides are grouped on the parameters tab.
Each row supplies Server, Variable Name and Value for that command. Use names such
as ``DEPLOY_MODULES`` and reference them as ``"${DEPLOY_MODULES}"`` in Bash. A variable
can appear only once per command/server. Names must match ``DEPLOY_[A-Z][A-Z0-9_]*``.

For bulk configuration, select **Parameter Servers** manually or click **Add All
Deployment Servers** to add all active servers, including those in maintenance
mode. Enter **Key** and **Value**, then click **Set Parameter**. This creates or
updates that key for the selected servers without changing other keys or servers.
Repeated clicks do not create duplicate rows. Selecting servers does not queue a
deployment or make a maintenance server eligible to run.

Leave the selection empty to save a shared command default in **Default
Parameters**. Each server uses its own value when present, otherwise the shared
default. Defaults also cover servers added later. Setting a default does not
overwrite existing server-specific values. Inputs are retained after applying;
changing inputs alone does not change the values used by deployment scripts.

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


At submission, a private lookup resolves the command defaults and the selected
server's overrides.
Referenced values become shell-quoted assignments inside each command's separate
Bash process. Values are data, not executable substitutions; keep references quoted
and do not pass them through ``eval``. Assignments are local shell variables, not
implicitly exported to child processes. Action and check commands have independent
parameter rows. Missing or empty referenced values block submission, including
references found in comments/literal text. Reserve ``DEPLOY_`` names for injected values;
use other names for local variables. This is not a Jinja or Python expression engine.

Resolved scripts are frozen for approval and retries. Catalog or server changes
apply to a later submission or the existing **Update Commands** approval workflow.
Existing frozen scripts remain unchanged; queue validation detects resolved
parameter changes requiring an approved script update.
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

## SSH test failure reports

**Test Selected SSH** and the row-level **Test SSH** show failed servers in a
sticky warning and add one internal chatter note to the deployment request.
Each failure has its configured **serial - server name** in bold red on a separate
line, followed by the translated SSH failure reason. Numeric serials sort
numerically; servers without a serial show only their name. The report includes
tested, successful and failed totals. Success-only tests and empty selections
do not add chatter notes. Testing does not change deployment selections or states.

## On-demand health collection

Health collection uses the existing approved SSH deployment workflow. There is no branch agent, inbound API, timer, heartbeat, incident tracking, or automatic remediation.

1. In Command Catalog, create your own **Post-deployment Check**, enable **Collect Health Report**, and enter its Bash script. Keep commands observational, use read-only database access where needed, and bound subprocess/HTTP/database execution with timeouts. This flag identifies the output contract; it does not sandbox arbitrary Bash commands.
2. The command must print exactly one block using the contract below. Put markers on their own lines. Use a JSON serializer when details contain quotes or newlines. Never print credentials, secret parameter values, customer data, raw HTTP bodies, or queue arguments into either JSON or ordinary command output.
3. Create a request with **Request Purpose = Health Collection**, add your collector checks and target servers, approve it once and assign its executor. Select servers and use **Run Selected Health Checks**. Use **Select All for Health Collection** to select all eligible servers.
4. Open **Reports → Health Reports** or the request's **Health Reports** tab. Each server execution has its own report, readable checks, JSON preview, and **Download JSON**. Servers show the latest report accessible to the current user and its collection time.

```bash
# Example only: create/configure your own command; no commands are installed automatically.
printf '%s\n' 'AB_DEPLOY_HEALTH_BEGIN'
printf '%s\n' '{"schema_version":1,"checks":[{"id":"odoo_service","status":"healthy","details":"Service is running","duration_ms":12}]}'
printf '%s\n' 'AB_DEPLOY_HEALTH_END'
```

The JSON object must contain `schema_version: 1` and a nonempty `checks` array. Every check requires a stable `id`, `status` (`healthy`, `warning`, `critical`, or `unknown`), and text `details`; integer `duration_ms` is optional. IDs are unique within a command and are namespaced by the frozen request-command line when combined. Details are limited to 4096 characters, collected JSON to 1 MiB, and combined results to 500 checks. Server identity and UTC collection times come from execution records, not command input. Report timestamps are serialized in Odoo's UTC date/time format with `timezone: UTC`.

A successful collector exits `0` even when it reports unhealthy services. A nonzero exit means the command itself failed. Health Collection requests continue remaining commands and preserve valid results alongside unknown collection errors. Execution status and reported health are separate. Missing, malformed, oversized, or interrupted output never implies healthy. Overall health uses Critical → Unknown → Warning → Healthy. Ordinary deployment requests keep their existing fail-fast execution behavior.

Reports are parsed from contiguous full downloaded command-output parts, not the recent-log preview. Resume Monitoring collects remaining output into the same report without replaying an existing remote execution. A new retry execution creates a new report. Repeated observations do not duplicate reports, and older executions cannot replace newer server snapshots. Failed SSH attempts also have an unknown/failed report. To collect again, reselect completed servers on the same approved request and click **Run Selected Health Checks**. Each run creates fresh execution keys, jobs, and reports without another request approval. Queued, running, unknown, or incompletely collected executions must finish or be resolved before another collection; active monitoring queue runs must also finish. The approved server list remains fixed.

When collector commands or resolved parameters change, the red **Update Commands** button appears for administrators on idle health targets, including completed servers. Review the script diff, enter an update reason, and confirm. This uses the existing administrator confirmation without a second request approval. The next run uses the revised script; earlier jobs and reports keep their original snapshots. Changed or invalid commands block execution until the update is confirmed.

Reports follow request participant/company permissions; administrators can see all permitted company reports. Binary downloads enforce the same record access. Report records cannot be created, edited, or deleted through public ORM calls. Maintenance servers remain excluded by the existing execution rules. Retain report history alongside existing immutable execution history; this release adds no retention cron.

Deployment: update the existing `ab_deploy` addon on the collector (`deploy19`) to `19.0.4.14.3`, using a targeted `-u ab_deploy`, then restart its Odoo and queue-runner services during an idle window. No monitoring code needs installing on branch servers. The confirmed first target is `proxmox-2`, whose current SSH/runtime settings are already in the deployment inventory. Configure your checks before the first collection; the module does not submit or execute a pilot request automatically.

## Collector worker limits and recovery

Deployment batches read the Odoo system parameter `ab_deploy.ssh_threads` once before startup. It defaults to **10 SSH threads** and accepts integers from **1 to 16**. Administrators can change it in Settings → Technical → Parameters → System Parameters. Changes apply to the next batch without a service restart; a running batch keeps its original value. Missing parameters fall back to 10; invalid values stop the batch before jobs are claimed. Module upgrades preserve administrator changes to the parameter. This setting applies to both normal deployments and health collections, independently of Odoo worker-process counts and memory limits. All worker threads start before executions are claimed. Startup failures leave jobs queued; interrupted claims with no committed launch intent return to queued. Launched executions retain unknown status until monitoring confirms their remote result. Outstanding received output is processed before interrupted attempts are finalized.

Cancelling a failed Job Queue record does not resolve its Deployment Execution Jobs. Cancel Older Waiting Executions and Queue cancels waiting executions only. Use Check and Resolve for unknown executions, checking the original remote execution key before resolving them. Recovery must retain completed jobs and reports and must never replay an uncertain remote launch.
