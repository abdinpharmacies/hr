# Deployment Manager

## Manually resolve a failed server

Open the failed record under **Execution Jobs** and choose **Mark as Manually Resolved**.
Executors and Deployment Administrators can confirm an external fix with a required
resolution note. The request must remain approved and no active queue run may handle
that execution. This is a human confirmation: Odoo does not run SSH checks or commands.

The job and target show **Manually Resolved** (تمت المعالجة يدويًا), separately from
Succeeded. The resolver, resolution time and note are readonly. The original exit code,
error, failure category, timestamps, logs and attempts are retained. This terminal state
is excluded from selection, SSH retry, monitoring and recovery; late worker observations
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
