Current changes before commit:

- Document the local Settings repair on `abdin_pos` (port 4097); no runtime source changes were needed.
- The database still served the retired Settings view with `central_url`, although the current Python model no longer defines that field.
- Addon discovery failed on old hidden `.uom_old_20261105` backup directories. Ten backups were moved intact to `/opt/odoo19/uom-backups/settings-repair-20261116-new/`. The remaining root-owned inventory-audit backup was subsequently absent from the addons path; its removal was not performed by this repair.
- Successfully upgrade only `ab_branch_sync` using the existing source, with isolated ports and cron disabled for the upgrade process. The retired Settings view is now inactive and no longer references `central_url`.

Files changed:

- ab_branch_sync/changelog.d/2026-11-16-settings-upgrade-repair.md

Verification:

- Targeted upgrade exited successfully; log: `/tmp/settings-branch-upgrade-20261116-retry.log`.
- Settings `get_views` passed for `en_US` and `ar_001`: all 71 top-level fields have returned field definitions, and neither form references `central_url`.
- Addon discovery successfully parsed 704 manifests.
- The running instance returned HTTP 200 at `/web/login`; no browser session was available for visual verification.
- No user-facing source strings changed; both existing Arabic catalogs were retained.

Recent relevant commit:

- Commit: 7de282deba0152168f1235803dd0d50690ca6510
- Author: hager yasser
- Date: 2026-11-11
- Original subject: ab_branch_sync/feat: move connection controls to operations and reset authorization when settings change
- Move connection controls to Operations and retire the previous Settings view.

Files changed:

- ab_branch_sync/README.md
- ab_branch_sync/changelog.d/2026-11-10-connection-controls.md
- ab_branch_sync/changelog.d/2026-11-11-button-rpc.md
- ab_branch_sync/changelog.d/2026-11-11-enrollment-reconciliation.md
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/ir_config_parameter.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/views/operations.xml
- ab_branch_sync/workflow.md
