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

In Command Catalog, set **Command Type** to **Deployment Action** or **Post-deployment
Check**. Existing commands default to Deployment Action; administrators choose which
scripts are checks. Draft requests may be incomplete, but new submissions require at
least one active check. Check-only requests are allowed.

Actions run first, followed by checks. Sequence and record ID order apply within each
category, matching the Commands list. At submission, command names, scripts, types and
order are frozen in each target snapshot with check policy version 1. Approval validates
that snapshot, not later catalog edits. Previously submitted/approved requests without
the policy marker retain their existing scripts, later batches and retries. Resubmitting
a draft applies the current policy; no checks are silently added to old deployments.

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
