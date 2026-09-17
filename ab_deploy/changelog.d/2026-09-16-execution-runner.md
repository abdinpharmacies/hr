# Deployment execution and server registry

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-16 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Retain release readiness, independent approval, target planning, and immutable audit history from the initial MVP.
- Extend `ab_deploy_server` with SSH aliases, CSV metadata, health URLs, executable paths, and monitoring timeouts. Add administrator-only CSV preview/import with stale-preview checks, unique aliases, preserved text identifiers, and existing-server protection.
- Add a Deployment Administrator-owned command catalog and ordered developer-selected release commands. Validate module names and shell-quote fixed placeholders; reject `base`/`all` and require backups for database-changing commands.
- Freeze settings, command definitions, parameters, generated scripts and checksums per target at submission. Template edits cannot alter reviewed scripts. Prevent scope edits and duplicate queueing after execution starts.
- Add persistent execution jobs, executor queueing, a separate runner role, authenticated JSON-2 claim/report methods, expiring leases, immutable results, and bounded reports. Audit state transitions without duplicating full log tails on every heartbeat.
- Add a standalone OpenSSH runner and systemd service template. Use verified host keys, non-root aliases, immutable Git commits, private remote history, detached tmux sessions, host locking, duplicate-launch prevention, and expiring launch grants.
- Add database/filestore and optional checkout backups, fail-fast execution, automatic service-start attempts after failure, original exit-code preservation, and service/HTTP/database/module-state health verification.
- Treat already-installed installs and already-absent uninstalls as no-ops. Reject uninstall cascades outside the selected modules, populated owned models, and module-owned business records in shared models.
- Respect deployment windows, wave ordering, concurrency and failure thresholds. Cancel pending work without killing active upgrades. Reconcile unknown jobs without automatically executing their scripts again; document manual recovery.
- Add native XML views, runner setup/operation documentation, and both Arabic translation files. Use underscore-only custom model names, no hooks, no cron jobs, and no external-database writes.
- Preserve Abdin Pharmacies authorship. The editor-layout follow-up sets the manifest developer to emadco88, now available from the current Git configuration.

## Validation

- Targeted upgrade passed on `ab_deploy_validation_20260910`; fresh installation passed on `ab_deploy_validation_execution_20260916`, with no demo data, isolated ports and cron disabled.
- 64 ORM/workflow/security checks passed, including settings-admin denial, snapshot immutability, token ownership, cancellation, waves, thresholds, future windows, parameter injection, and CSV validation.
- 18 local Bash/tmux checks passed using isolated fake Git/service/Odoo commands and a dedicated tmux socket: backup gating, failure recovery, original exit codes, concurrent locks, duplicate launches, unknown outcomes, and expired launch grants.
- Four authenticated JSON-2 checks passed against a temporary localhost Odoo instance: unauthorized claim rejection, valid claim, invalid lease rejection, and report delivery. The temporary API credentials were revoked and the test HTTP process stopped.
- Real disposable-Odoo module-operation checks passed for absent-module uninstall, already-installed install, dependent-module protection, and preservation of module-owned records in shared business models.
- Exported the POT from Odoo 19, merged translations without replacing unrelated entries, and validated both PO files with `msgfmt --check-format`. Both now contain 309 entries. Runtime `ar_001` verification passed for Command Catalog and Update Approved Code.
- The actual `deployment_script/servers.csv` successfully previewed all 59 rows on the disposable database; no import was applied.
- The systemd unit passed `systemd-analyze verify`.
- Validation scripts/results remain outside the addon under `/tmp/ab_deploy_execution_*`, `/tmp/ab_deploy_engine_*`, `/tmp/ab_deploy_http_*`, and `/tmp/ab_deploy_runtime_*`.
- No branch server was contacted. No runner service was installed or activated, and no production database was upgraded. The provided CSV was inspected, not imported into a live database.

Files changed:

- `ab_deploy/__init__.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/changelog.d/2026-09-10-deployment-manager-mvp.md`
- `ab_deploy/changelog.d/2026-09-16-execution-runner.md`
- `ab_deploy/data/commands.xml`
- `ab_deploy/data/sequences.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/commands.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/runner/README.md`
- `ab_deploy/runner/ab-deploy-runner.service`
- `ab_deploy/runner/engine.py`
- `ab_deploy/runner/service.py`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/security/security_groups.xml`
- `ab_deploy/static/description/icon.png`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/execution_views.xml`
- `ab_deploy/views/menus.xml`
- `ab_deploy/wizard/__init__.py`
- `ab_deploy/wizard/server_import.py`
- `ab_deploy/wizard/server_import_views.xml`
