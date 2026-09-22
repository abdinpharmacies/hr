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
