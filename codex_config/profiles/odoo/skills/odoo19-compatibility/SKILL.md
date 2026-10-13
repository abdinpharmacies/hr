---
name: odoo19-compatibility
description: Check or migrate changed Odoo code for version 19 ORM, XML views, Owl, JavaScript, assets and external API compatibility.
---

Read the [verified compatibility matrix](references/compatibility.md) and inspect
installed 19.x code before calling a construct unsupported. Distinguish official
behavior, project conventions and corrected historical observations.

- Use `<list>`, action `view_mode="list,form"`, and Kanban `t-name="card"`.
  Replace view `attrs`/`states` with direct Python modifier expressions.
- Distinguish Python modifiers, JavaScript QWeb Kanban and Owl expressions.
  Move handler statement logic into methods. Prefer `!`, `&amp;&amp;`, `||` in
  this project; Owl's `and`/`or` aliases exist, but Python `not` is not one.
- Use native ES modules and manifest asset bundles. Retain the project's
  `/** @odoo-module **/` convention; standard source/test folders auto-transpile.
  The supported legacy loader is not universally removed.
- Use `models.Constraint`, `fields.Domain`, documented domain operators and
  `aggregator`. Serialize Domain with `list()` for legacy transports. Do not
  confuse valid Python/XML `==` with domain operator `=`.
- Replace `odoo.osv`, `_cr`, `_uid`, `_context` with current APIs. Avoid new legacy
  external XML-RPC/JSON-RPC integrations; assess JSON-2. Current application
  controllers with `type='jsonrpc'` are not covered by that deprecation.

Validate changed views via targeted installation/upgrade and affected bundles at
runtime. Return file/symbol, evidence and minimum correction. Do not automatically
repair unrelated modules named in historical snapshots.

When investigating a named historical regression, consult
[repository and session history](references/repository-history.md) only as leads;
the verified matrix governs current compatibility decisions.
