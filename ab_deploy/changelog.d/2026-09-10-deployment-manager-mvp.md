# Deployment Manager MVP

Historical development record. See `2026-09-16-execution-runner.md` for current uncommitted scope.

Commit: uncommitted (new module; no prior module commits)
Author: pending — this checkout has no configured Git user identity
Date: 2026-09-10 (UTC)
Original commit subject: not applicable; no commit created

## Initial MVP scope (historical, 2026-09-10):

- Add server registration, release readiness, deployment requests, wave-based target planning, and approval reports.
- Use underscores in all five persistent custom model names and the internal abstract guard model.
- Require an independent approver, including for administrator-created requests; record rejection, withdrawal, and cancellation reasons.
- Freeze referenced releases and server configuration during review/approval; invalidate approval after request scope changes.
- Protect state fields against direct writes, imports, and injected context defaults. Lock affected records during workflow changes.
- Retain audit history and server/release/request records. Allow removal of draft target lines with a retained audit event.
- Restrict access to explicitly assigned central deployment roles. These roles intentionally see all deployment records; ordinary branch users have no access. No additional row restrictions are required for this central-team MVP.
- Hide SSH key references and host fingerprints from non-administrators and omit them from audit payloads.
- Add Odoo approval activities, native XML views, and Arabic translations in both supported translation files.
- Defer SSH execution, live health checks, backup execution, rollback execution, and Telegram delivery.
- Preserve Abdin Pharmacies authorship. Manifest developer remains UNCONFIGURED until the current developer name is supplied; do not infer identity from historical commits.

## Validation

- Fresh installation and targeted upgrades passed on disposable database `ab_deploy_validation_20260910` using alternate ports 5069/5072 and no cron workers.
- 79 checks passed: business validation, independent approval, scope invalidation, context-default bypass rejection, multi-record actions, unauthorized access, immutable audit history, and native view compilation for four roles.
- Exported the POT from Odoo 19. Both Arabic files contain 198 translated entries and pass `msgfmt --check-format`.
- Runtime `ar_001` verification: Deployment Requests → طلبات النشر; Deployment Manager → إدارة النشر.
- Test fixtures and test code remain outside the production addon; fixture transactions were rolled back.
- Development evidence: `/tmp/ab_deploy_validation.py`, `/tmp/ab_deploy_validation_results.txt`, `/tmp/ab_deploy_install.log`, `/tmp/ab_deploy_upgrade_final.log`.
- No production database was upgraded and no branch server was contacted.

Files changed:

- `ab_deploy/__init__.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/security/security_groups.xml`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/data/sequences.xml`
- `ab_deploy/views/menus.xml`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/static/description/icon.png`
- `ab_deploy/changelog.d/2026-09-10-deployment-manager-mvp.md`
