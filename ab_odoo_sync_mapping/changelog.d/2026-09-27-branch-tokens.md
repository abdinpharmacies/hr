# Branch tokens and reporting receiver contention

Recent relevant commit: `19dca67c675fcca6d557d0652fb18fd281207fc7`
Author: emadco88
Date: 2026-09-25
Original subject: ab_odoo_sync_mapping/ FIX sticky hdd-serial

- Preserved sticky approved hardware binding and existing security actions.
- Inspected this commit and the current working diff before this update.

Current changes before commit:

- Exchange branch keys for 15-minute opaque tokens; store digests only.
- Validate branch, hardware, scope, expiry, and credential generation on every request.
- Revoke tokens when credentials, hardware, active state, or branch identity changes.
- Keep legacy key requests enabled during rollout, with an explicit disable switch.
- Prevent RPC calls to receiver methods from bypassing controller authentication.
- Avoid row locks for unchanged approved hardware and throttle upload timestamps.
- Log authentication mode and timings without credentials; reuse autovacuum for token cleanup.
- Add Arabic translations and least-privilege token ACLs.

Validation:

- Fresh isolated installation and targeted production upgrade passed.
- 19 model/security/batching checks passed across receiver and sender.
- HTTP tests passed with two workers, including cross-worker revocation and replay idempotency.
- Synthetic six-request-per-second workload: upload p95 24.59 ms, authenticated list-read p95 9.61 ms.
- Arabic field/action translations verified with ar_001. Test scripts are retained outside runtime addons in `/opt/odoo19/validation/sync_tokens`.

Files changed:

- `__manifest__.py`
- `controllers/report.py`
- `models/__init__.py`
- `models/ab_odoo_sync_token.py`
- `models/ab_odoo_sync_branch_registry.py`
- `models/ab_odoo_sync_mapping_service.py`
- `security/ir.model.access.csv`
- `views/configuration_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-09-27-branch-tokens.md`
