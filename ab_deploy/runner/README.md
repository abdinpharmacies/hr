# Approved custom commands through queue_job

`ab_deploy` uses OCA `queue_job`. There is no custom deployment daemon or API key. The `runner/` Python files are imported helpers, not services.

## Setup

Assign Developer, Approver, Executor, Viewer and Deployment Administrator roles independently. Administrators maintain the command catalog; developers select and order plain Bash commands. A requester cannot approve their own request, including administrators.

Run the dedicated Odoo queue service as Linux user `odoo19`, with the same code, database and filestore as the main service. On this installation SSH aliases belong in `/opt/odoo19/.ssh/config`. SSH can use any remote account, including root. `BatchMode=yes` requires unattended authentication; `StrictHostKeyChecking=accept-new` records new host keys and rejects changed ones. Keep SSH files private and owned by `odoo19`.

The queue service loads `base,web,queue_job`, uses two Odoo workers, a localhost HTTP port, and `max_cron_threads = 0`. The main service retains scheduled actions and must not start another queue runner. Queue configuration:

```ini
[options]
limit_time_real = 3900

[queue_job]
channels = root:2,root.deployment:1
host = 127.0.0.1
port = 4091
```

One deployment channel slot runs one batch job with up to 70 SSH threads. It does not require 70 Odoo processes. The application waits at most one hour; the worker limit leaves a five-minute margin. `deployment_script/setup_odoo19_queue_runner.sh` includes this setting for new services. Update an existing queue configuration manually. Stop both Odoo services for a shared-database module upgrade; restart them afterwards. Disable the obsolete `ab-deploy-runner.service` if still installed.

Branches need Bash, tmux, flock, GNU date/dd/stat, base64, sha256sum, and a writable SSH-account home. The commands themselves determine whether Git, sudo, PostgreSQL or Odoo are needed.

## Approval and queueing

Commands are plain Bash without placeholders. They start in the remote account's home, execute in order in separate subshells, and use `set -e -o pipefail`. Variables and directory changes do not carry between catalog commands. A nonzero exit prevents later commands from running.

Create a Deployment Request with an approver, commands and target-server rows. Add All Production Servers appends eligible production servers without duplicates; individual servers can also be added manually. Readiness and backup-policy fields are informational. Approval submission freezes commands, SSH aliases, paths and monitoring timeouts. Subsequent server/catalog edits affect future submissions only.

When an Executor queues a request, overlapping queued/running/unknown executions trigger a confirmation wizard. Choose to cancel older **unstarted executions on overlapping servers only**, queue behind them, or go back. Executors and Administrators can replace waiting executions belonging to another developer; the actor and replacement request are recorded. Other servers and running scripts are not cancelled. Changed conflicts require confirmation again.

All targets begin delayed and unselected. After approval, the executor checks Deploy on individual rows or uses Select All for Deployment / Clear Deployment Selection. Queue Selected Servers creates jobs only for the selection; remaining delayed targets can be queued later under the same approval. Each batch clears its selection. Targets with existing execution jobs cannot be selected again. One `ab_deploy_job` is created per selected target. One `ab_deploy_run` and one `queue.job` handle the batch. No periodic coordinator records are generated. Up to 70 hosts run concurrently, with additional hosts filling free slots. Other hosts continue when one fails. Queued work respects earlier executions on the same server. A waiting batch can monitor stale running/unknown blockers without rerunning them.

Odoo server locks and the remote account lock prevent overlapping launches. Different aliases for one account are protected by the remote lock; different remote accounts have independent locks. Cancelling a request affects queued targets only; running commands continue.

## Progress and logs

SSH threads pass plain events through a bounded queue; they never use ORM records or cursors. The job's main thread writes progress through short independent database transactions. It never commits the transaction owned by queue_job. Launch intent is committed before launch side effects.

The monitor stays connected through SSH, sending status and log chunks every two seconds. Manually refresh the request to see Waiting, Connecting, SSH Connected, Script Created, Tmux Started or Script Running, together with result, failure category and last check. Waiting executions link to their blockers.

Each target has a stable key, session `deploy_<key>`, and private directory `~/updates/<key>/` containing script, output, status and timestamps. An existing directory is never overwritten or relaunched. Sessions exit naturally. No code calls `tmux kill-server` or `tmux kill-session`.

Odoo stores complete command output as ordered immutable attachments, a 64 KiB preview, and connection-attempt history. SSH diagnostics are bounded to 16 KiB per attempt. Downloads resume by byte offset; concatenate parts in order for complete output. A part can split a line.

## Retries and recovery

After the previous batch releases the execution, Executors and Administrators can use **Retry SSH Failure** on selected executions or **Retry SSH Failures** on a request. One new queue job handles the selected retry batch, reusing approved commands/settings and preserving history. A failed side-effect-free SSH preflight can retry launch. After persisted launch intent, reconnection only monitors the existing key; it never blindly relaunches. Successful targets remain untouched. Setup errors and confirmed nonzero command exits require a new approved request.

**Resume Monitoring** handles unfinished executions and incomplete logs. It may launch queued targets never attempted; previously attempted targets are observed only. A per-server deadline (default 600 seconds, frozen at approval), or the overall one-hour deadline, stops observation without terminating remote tmux. Waiting targets remain queued for later resumption. Ten minutes is a monitoring default, not a guaranteed upgrade duration.

The Administrator's **Recover Deployment Jobs** action uses the same deduplicated scheduling and does not alter other modules' jobs. No new cron is installed. OCA queue_job retains lock-based dead-worker recovery; redelivery reconciles persisted progress before continuing. Existing serialized `_run_tick` and `_coordinate` tasks hand work to a batch without recreating the old polling loop.

Unknown executions continue blocking their servers until confirmed finished or explicitly resolved. **Resolve Execution** requires an inspection note, rechecks SSH, and refuses while the remote tmux session is alive. It does not terminate processes. Queue-job completion means observation finished, not necessarily that every command succeeded.

CSV `server` maps to SSH alias. The legacy CSV `timeout` is informational; new server monitoring timeouts default to 600 seconds, preserving existing settings.

## Validation

Use mocked SSH and temporary files. Never use real branch servers or real tmux sessions in automated checks. Test fixtures remain outside the addon.

## Optional Odoo log capture

In **Servers → Odoo Paths**, defaults are:

- Odoo Log Path: `/opt/odoo19/odoo.log`
- Odoo Server Path: `/opt/odoo19`
- Odoo Server Config: `/opt/odoo19/odoo19.conf`
- Odoo Python Venv: `/opt/odoo19/venv19/bin/python`

Enable **Get Recent Odoo Log** on a draft deployment. Requesting approval requires all four paths on every selected server; paths must be absolute without control characters. The settings are frozen with the approved script. Server/config paths are informational; capture uses the log and Python paths. Commands remain plain Bash: these fields do not rewrite commands or select a database.

The remote wrapper starts a standalone Python collector before commands. It collects new WARNING, ERROR and CRITICAL records, including multiline tracebacks, from the script's start through its finish. It expects standard Odoo UTC log headers. Shared log files may contain activity from other databases. INFO/DEBUG entries are excluded. Python and the log must be accessible to the SSH account; Bash, GNU date/dd, base64, nohup, flock and tmux are also required.

Capture starts at the existing file's end, follows newly created files, and detects rotation and truncation. The execution displays a warning when capture may have gaps. Entries removed between polls or written to a rotated file after it has been closed cannot be recovered. Missing Python, unreadable logs and collection errors do not alter the command exit code.

Execution Jobs show collection status, remote capture times, notes and a 64 KiB preview. The SSH stream downloads at most 256 KiB per log per server every two seconds and stores ordered immutable log parts as attachments. There is no total-size truncation; concatenate parts by their byte offset for the complete filtered output. Parts can split lines. Log parts have the same Deployment Viewer read access as execution jobs.

Collection continues after command completion. After five unavailable/no-progress checks, collection stops with a separate error. **Recover Deployment Jobs** resumes downloads from the saved byte offset, including completed executions, without rerunning their commands. Old snapshots and deployments with the checkbox disabled retain their original behavior.
