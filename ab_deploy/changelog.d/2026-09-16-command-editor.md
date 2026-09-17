# Command editor layout

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-16 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Move Bash Template out of the narrow form group into a full-width editor with a visible rounded border, monospace text, a 360px height and internal vertical/horizontal scrolling.
- Keep Bash left-to-right, preserve script whitespace, and support read-only viewing and narrow screens using the existing Odoo text widget.
- Replace the help paragraph with a separate information panel, wrapping placeholder badges and concise quoting/recovery guidance.
- Use an inherited XML view and module-scoped backend SCSS; shared frontend widgets and deployment execution logic are unchanged.
- Append the new help translations in both Arabic catalogs after exporting the module POT from Odoo 19; preserve existing entries and literal placeholder names.
- Set manifest developer to the current Git user, emadco88, while retaining Abdin Pharmacies as author. Refresh the execution changelog's ownership and repository-state notes.

## Validation

- Targeted upgrade passed on disposable database `ab_deploy_validation_20260910` with isolated ports and cron disabled.
- Browser checks passed at desktop and mobile widths: full-width layout, fixed height, both scroll directions, exact saved whitespace, Arabic help with left-to-right Bash, read-only display, and no browser errors.
- SCSS compilation and both `msgfmt --check-format` checks passed. Runtime Arabic verification was performed in the browser.
- Evidence: `/tmp/ab_deploy_editor_browser_results.txt`, `/tmp/ab_deploy_editor_desktop.png`, `/tmp/ab_deploy_editor_mobile.png`, `/tmp/ab_deploy_editor_arabic.png`, and `/tmp/ab_deploy_editor_upgrade_final.log`.
- Browser fixtures and scripts remain outside the addon. No production database was upgraded and no branch server was contacted.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/views/command_editor_views.xml`
- `ab_deploy/static/src/scss/command_editor.scss`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-16-command-editor.md`
- `ab_deploy/changelog.d/2026-09-16-execution-runner.md`
