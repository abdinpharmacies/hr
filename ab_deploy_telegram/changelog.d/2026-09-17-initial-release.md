# Deployment Telegram summaries

Commit: uncommitted (new module; no previous commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Add opt-in Telegram notification settings to deployment requests with subscription defaults and per-request overrides frozen on approval submission.
- Queue approval, selected-batch and batch-outcome summaries including serial/name, failure category, unfinished and delayed counts, and an Odoo link.
- Keep notification work outside SSH threads and deployment queue capacity; delivery failures never alter deployment results.
- Add company-scoped deployment record rules and read-only Telegram access for deployment roles; retain token and configuration control under Telegram administrators.
- Add both Arabic catalogs, configuration documentation and inherited views without modifying ab_deploy.

## Validation

- Installed both modules on deploy19 and ran targeted upgrades using --no-http --stop-after-init.
- Corrected an initial Odoo 19 ir.module.module ondelete constraint; final upgrade exited 0 without ERROR/CRITICAL/traceback entries.
- Exported POT catalogs from the installed modules and populated ar.po and ar_001.po.
- No extra functional tests, real Telegram sends, bot credentials or group configuration were used.
- Existing duplicate Target Servers label warning in ab_deploy remains.

Files changed:

- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/__init__.py`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/models/__init__.py`
- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/security/security.xml`
- `ab_deploy_telegram/static/description/icon.png`
- `ab_deploy_telegram/views/deployment_views.xml`
- `ab_deploy_telegram/changelog.d/2026-09-17-initial-release.md`
