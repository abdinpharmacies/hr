# Queue-based custom command deployments and batch recovery

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Merge release planning and approval into Deployment Requests with ordered catalog commands, frozen target scripts and informational readiness fields. Remove Git/Odoo configuration requirements, automatic backups, health checks, windows, waves and failure thresholds.
- Replace the external API runner with queue_job. Keep plain Bash catalog editing administrator-only, independent human roles, self-approval rejection, and explicit Executor queueing.
- Dispatch up to 70 SSH connections concurrently in a bounded thread pool. Threads receive plain payloads; only the coordinator accesses the ORM. Launch and monitoring use separate short queue jobs.
- Preserve remote job identifiers and directory-based duplicate protection. Record completion from exit status, retain logs, serialize each server, and keep Unknown outcomes blocked until reconciled or inspected.
- Retain the first queue-based release's `_run_tick` entry point for pending serialized tasks. Add an administrator recovery menu that deduplicates coordinator tasks, imports remote results, resumes live monitoring and preserves uncertain outcomes. Other modules' queues and terminal deployments are not replayed.
- Add an editable remote-inspection resolution wizard. No deployment code kills tmux sessions or servers.
- Preserve the CSV format, default new monitoring deadlines to 600 seconds regardless of legacy CSV connection timeouts, and retain existing deadlines during import.
- Complete plain-Bash editor help and both Arabic catalogs using exported POT references, preserving all existing message IDs. Rewrite setup/recovery documentation and bump the module to 19.0.3.1.0.

## Validation

- Fresh queue-based installation and subsequent targeted upgrades passed on disposable database `ab_deploy_queue_validation_20260917`.
- Initial queue workflow checks passed (31 assertions). Final coordinator/recovery tests passed (23 assertions), including 70 simultaneous mocked SSH calls, old pending-job compatibility, repeated recovery, lost acknowledgements, per-server serialization, cancellation, and recovery of 71 Unknown executions exactly once.
- Eight safe engine checks passed using a fake tmux executable, including ordered Bash, nonzero exits, duplicate delivery, partial uploads, malformed monitoring output, and bounded parallel handling of slow/unreachable hosts. No real tmux executable or branch SSH connection was used for these final tests.
- Both Arabic catalogs passed format checks and exported-string coverage; Arabic action/menu names and four combined form views were verified at runtime on the disposable database.
- Python/XML syntax and diff whitespace checks passed. Temporary test fixtures remain outside the addon and ORM fixtures were rolled back.
- Read-only audit of `deploy19` found one pending legacy `_run_tick` task and one queued deployment. They were not executed or modified; recovery follows the user's manual upgrade.
- Operational configuration: `/opt/odoo19/odoo19.conf` now specifies `root:2,root.deployment:1`, retaining three Odoo workers. The service already loads `base,web,queue_job`. No services restarted or live databases upgraded.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/commands.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/runner/README.md`
- `ab_deploy/runner/service.py` (removed)
- `ab_deploy/runner/ab-deploy-runner.service` (removed)
- `ab_deploy/data/commands.xml` (removed)
- `ab_deploy/data/sequences.xml`
- `ab_deploy/data/queue_jobs.xml`
- `ab_deploy/security/security_groups.xml`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/execution_views.xml`
- `ab_deploy/views/command_editor_views.xml`
- `ab_deploy/wizard/__init__.py`
- `ab_deploy/wizard/server_import.py`
- `ab_deploy/wizard/server_import_views.xml`
- `ab_deploy/wizard/resolution.py`
- `ab_deploy/wizard/resolution_views.xml`
- `ab_deploy/wizard/recovery.py`
- `ab_deploy/wizard/recovery_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-queue-deployments.md`
