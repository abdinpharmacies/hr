# Required post-deployment checks

Recent relevant commit: f314539ceb829c0844e30d6070ef11aae5720715
Author: emadco88
Date: 2026-09-22
Original commit subject: ab_deploy/ UPD - Add audited manual resolution and admin undo for failed deployments; update statuses, sorting, and Telegram reports
- Added audited manual resolution for failed deployments.

## Current changes before commit:

Author: emadco88
Date: 2026-09-22 (UTC)
Commit: uncommitted

- Add Deployment Action/Post-deployment Check command types, defaulting existing commands to actions.
- Require at least one active check for new submissions; allow check-only requests and keep drafts editable/incomplete.
- Freeze names, types, script and effective action-first/check-last ordering with policy version 1. Validate marked snapshots at approval; preserve pre-policy submitted/approved scripts and retries.
- Show command types and effective ordering in the request, preserving approved line types after catalog edits.
- Add safely quoted START/END log markers and isolated fail-fast Bash execution; preserve explicit exit codes and stop subsequent commands on any failure.
- Update command help, documentation, both Arabic catalogs and version 19.0.4.3.0.
- Earlier uncommitted individual/selected SSH test changes are documented separately in their 2026-09-22 entries.

Validation: targeted upgrade exited 0 without ERROR/CRITICAL/traceback. Rolled-back ORM checks passed for required/active checks, check-only requests, type ordering, frozen snapshots after catalog edits and pre-policy snapshots. Harmless local Bash checks passed for all-success, action failure, check exit 1/2, pipefail, explicit exit 0, stdin use and quoted command names. Arabic view verification passed. No deployments, SSH calls or Telegram messages were performed; validation records rolled back. msgfmt unavailable.

Files changed for this feature:

- `ab_deploy/models/commands.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/views/command_type_views.xml`
- `ab_deploy/views/command_editor_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-22-post-deployment-checks.md`
