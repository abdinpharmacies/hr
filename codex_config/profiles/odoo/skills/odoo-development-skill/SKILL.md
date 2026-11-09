---
name: odoo-development-skill
description: Consult the bundled Odoo 14–19 pattern library for a specific Odoo implementation pattern, architecture review, or version upgrade comparison. Use inside the Odoo profile after checking the project's instructions and installed Odoo source. Skip for routine edits already covered by the focused Odoo skills.
---

# Odoo development reference library

This skill provides a broad upstream pattern library. Its examples are research leads, not verified templates for the current project or Odoo 19. Read only the files relevant to the task.

## Workflow

1. Read applicable `AGENTS.md`, the affected module's manifest, the current diff, and the relevant existing code. Use the repository's installed Odoo version. This profile normally targets Odoo 19; confirm the version when the task concerns another codebase or an upgrade.
2. Use the focused profile skills for their subjects: `odoo-module-development` for implementation, `odoo19-compatibility` for Odoo 19 syntax, `odoo-security-review` for access, `odoo-translation` for localization, and `odoo-testing-validation` for verification. The project's instructions and current Odoo source take precedence over this library.
3. Search `skills/` for one or two files matching the requested topic. For Odoo 19, prefer a matching `-19.md` file when present, but verify each example against installed Odoo code and the project's conventions. For upgrades, compare the source and target versions and use migration files only when the task actually concerns a deployed version.
4. Inspect Odoo core, installed addons, and relevant OCA modules when the feature or compatibility question warrants it. Do not turn every small edit into an exhaustive web search, add dependencies automatically, or generate scaffolding that the task does not need.
5. Treat `agents/` as optional reference checklists for a requested review, upgrade analysis, context study, or pattern search. They do not require spawning agents or adding new artifacts.

## Known limits of the upstream examples

Some bundled Odoo 19 pages still show `tree,form`, `_sql_constraints`, dotted custom model names, direct SQL updates, and old group or module scaffolds. Other pages claim that Python 3.12, type hints on every method, the SQL builder for every query, or OWL 3 are mandatory. Do not copy those claims or snippets without checking the installed version and the project's rules.

For the local `ab_*` pharmacy addons, follow the repository's `AGENTS.md` and `ab_template`: keep English UI source strings and both Arabic translation files, use underscores in custom model names, keep security configuration in `security/`, use `models.Constraint` and Odoo 19 list views, and do not add demo data, hooks, migrations for disposable development state, or direct inventory/external-database writes. Preserve branch isolation and inventory integrity. Use targeted module upgrades only when authorized.

Follow the user's requested language and the project's communication rules. Do not add code comments unless requested or essential to explain a non-obvious reason. Skill invocation does not authorize commits, deployment, external messages, or live database writes.
