# Odoo 19 custom addons: callcenter19

Checkout: `/opt/odoo19/worktrees/callcenter19`. Branch at consolidation: `callcenter19`;
verify the current branch and working diff before editing. Preserve unrelated work.

## Shared instructions

The existing ai-workflow Odoo profile is the shared authority. If the session
already supplies `Odoo 19 Custom Development` and `Odoo Review Rules`, use them
without duplicate reads. Otherwise read the [shared entrypoint](/home/abdin_04/Documents/projects/ai-workflow/my_ai_workflow/codex_config/profiles/odoo/instructions/entrypoint.md)
and its core/review references before Odoo work. The same entrypoint indexes
focused skills when they are absent from session discovery. Read only relevant
skills/references, not the conversion history or SQL packs by default.

For addon edits, read [module development](/home/abdin_04/Documents/projects/ai-workflow/my_ai_workflow/codex_config/profiles/odoo/skills/odoo-module-development/SKILL.md).
It includes required changelog, developer metadata and packaging checks. Keep
English source UI strings and both Arabic catalogs; apply the translation skill
when strings change. Security, inventory, pricing and branch/company invariants
remain mandatory under the shared rules.

## Runtime and local safeguards

| Service | Source / branch | Config | Database | Reserved HTTP port |
| --- | --- | --- | --- | --- |
| POS | `/opt/odoo19/worktrees/pos19` / `pos19` | `/opt/odoo19/conf/pos19.conf` | `abdin_pos` | `4091` |
| Callcenter | `/opt/odoo19/worktrees/callcenter19` / `callcenter19` | `/opt/odoo19/conf/callcenter19.conf` | `callcenter` | `4092` |

`/opt/odoo19/custom-addons` is the reports19 checkout, not the POS/callcenter
runtime source. For their sales flow, inspect and operate on the matching runtime
worktree first. Keep database/runtime fixes separate from source edits; do not
edit Odoo module files unless the user explicitly requests source changes.

This checkout is the mapped callcenter source; verify the runtime addons path before edits.

- Ports `4091` and `4092` are reserved for the user's PyCharm-managed processes.
  Never bind a temporary agent process to either unless explicitly requested.
- Never stop/restart the user's Odoo process to free a port. For upgrades, tests,
  asset checks and temporary servers, specify both `--http-port=5069` and
  `--gevent-port=5072`, with `--workers=0 --max-cron-threads=0`, or choose another
  unused pair. Check occupancy first; do not terminate an existing process.
- Prefer `--stop-after-init` when live HTTP is unnecessary. Track any temporary
  server's PID/session, stop only that server before finishing, and verify its
  HTTP/gevent ports are released with `ss -ltnp`.
- Verify readable config, actual addons paths, authorized database and configured
  log before validation. Alternate ports do not isolate database writes. Use
  targeted installs/upgrades, never `-u base`, and inspect logs and test counts.
