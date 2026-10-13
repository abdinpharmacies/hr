---
name: odoo-module-development
description: Implement or debug Odoo 19 ab_* addons, including scaffold, manifests, ORM, XML, dependencies and module packaging.
---

Inspect applicable AGENTS.md, the working diff, affected manifest and nearest
`ab_template`. Trace model/view/security/data relationships and downstream callers.
Keep the smallest valid diff in the owning module. Telegram messages belong in
`ab_telegram_bot` unless another module is explicitly named.

1. Implement Python, security, views/actions/menus, required data, then tests.
   Read [module conventions](references/module-conventions.md) for scaffold and
   manifest details. Set new manifests' `developer` string to `git config user.name`;
   retain company/team `author`. Recheck both before finishing a new module.
   Assignment syntax is not a dictionary entry.
2. Use recordsets, batched queries, `mapped`, `filtered`, `sorted`; preserve
   multi-record contracts and `super()`. Import model files in `models/__init__.py`.
   Avoid per-record queries and unrelated loop side effects. Prefer ORM and
   `env.cr`, `env.uid`, `env.context` over deprecated aliases.
3. Declare required cross-module relations in `depends`. For optional integrations
   check model availability and handle absence without silently granting access.
   Python constraints alone cannot enforce read isolation. Read
   [ownership and dependencies](references/ownership.md).
4. Define UI in XML. Inherit existing views with stable anchors, avoiding positional
   XPath. New models may need root views. Load records/files in dependency order;
   actions must exist before referencing menus. Scope frontend classes/templates
   to this module and register assets in the manifest.
5. Apply compatibility, security, translation and validation skills as needed.
   Use targeted fresh install/upgrade on an authorized development database.
   No demo files or hooks/migrations for disposable development state.
6. Maintain module `changelog.d` using [change records and hotfixes](references/change-records.md).
   Keep tests in development/CI; exclude them from runtime production packages.

Follow PEP 8, descriptive names, existing type hints and simple structures. Do not
replace ORM models with dataclasses. Use the project's venv and pinned requirements;
verify compatible dependency versions before adding packages, not blindly latest.
Preserve meaningful comments; avoid decorative comments, allowing essential rationale
and tooling annotations. For board/card/checklist work use the shared
[trello-workflow](../../../../shared/skills/trello-workflow/SKILL.md) skill.
Skill invocation does not authorize messages, commits, deployment or live DB writes.

For work on the corresponding UI modules, consult only the relevant historical
[self-inventory](references/self-inventory-history.md) or
[core UI](references/core-ui-history.md) reference. Verify the current code;
old completion claims and pending steps are not present facts or authorization.
For archival/pricing implementation, see [data protection](references/data-protection.md).
