# Verified Odoo 19 Compatibility

Checked 2026-09-24 against official 19.0 documentation and local
`/opt/odoo19/server`. Recheck installed code when a documented example conflicts
with runtime behavior. These are targeted-change checks, not a mass rewrite plan.

| Area | Verified behavior and project decision | Evidence |
| --- | --- | --- |
| Lists/actions | Use `<list>` (formerly tree), `view_mode=list,form` without spaces. | [Views](https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html), [Actions](https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html) |
| Kanban | Root template is `card`. Kanban templates are JavaScript QWeb, not Owl; do not add Owl-only `t-on-click` to them. | Views, Kanban/templates |
| Modifiers | Direct `invisible`, `readonly`, `required` Python expressions; fields used by expressions must be present in the view. `attrs`/`states` are rejected. | Views/Python expression; official source `odoo/addons/base/models/ir_ui_view.py`, `_check_xml` |
| Owl | XML templates contain JavaScript expressions, not arbitrary statement blocks. Move multi-statement handlers to component methods. Escape `&` as `&amp;`. Prefer JS operators; Owl also supports `and`/`or` aliases, not Python `not`. | [Odoo Owl](https://www.odoo.com/documentation/19.0/developer/reference/frontend/owl_components.html), [Owl 2.8.2 templates](https://github.com/odoo/owl/blob/v2.8.2/doc/reference/templates.md); installed `addons/web/static/lib/owl/owl.js`, `WORD_REPLACEMENT` |
| JS | New files use native imports/exports. `/static/src` and `/static/tests` auto-transpile; `@odoo-module` opts other folders in. Retain the project's annotation convention. `odoo.define` still exists for legacy files and generated output; it is not a blanket removed API. | [JS modules](https://www.odoo.com/documentation/19.0/developer/reference/frontend/javascript_modules.html) |
| Assets | Declare JS/XML/CSS/SCSS in manifest `assets`. No new legacy assets.xml bundles. Build and inspect affected bundles. | [Assets](https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html) |
| Constraints | Define `_unique_code = models.Constraint(...)` descriptors; `_sql_constraints` is no longer supported in this checkout. Preserve database/XML identifiers when migrating deployed constraints. | [ORM](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html), [ORM changes](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm/changelog.html); official source `odoo/orm/model_classes.py` |
| Domains | Use `fields.Domain`, `&`, `\|`, `~`, `Domain.AND/OR`; combiners return Domains. `list(domain)` serializes. Use documented lowercase comparison names and `=`/`!=`; do not use `==`/`<>` as domain operators. Python modifiers may use `==`. | ORM/Search domains; installed `odoo/orm/fields.py`, `odoo/orm/domains.py`; verified import `from odoo import fields` |
| SQL | The SQL wrapper is supported, not deprecated. The project's restriction means prefer ORM and avoid arbitrary SQL/domain injection; any necessary SQL must be parameterized and explicitly enforce access/scope. | ORM/SQL execution and ORM changes |
| Deprecations | Replace `odoo.osv`, `record._cr`, `_uid`, `_context` with supported APIs (`env.cr`, `env.uid`, `env.context`). `group_operator` became `aggregator`. For new aggregation assess `_read_group` or public `formatted_read_group` instead of deprecated `read_group`. | ORM changes, 19.0 / 18.2 / 17.2 |
| Security groups | Project order is category -> `res.groups.privilege` -> `res.groups.privilege_id`. The 19.0 security prose still describes older `category_id`; inspect actual official 19.0 model when following examples. | [Security](https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html); [official res_groups.py](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/models/res_groups.py) |
| External APIs | Legacy external `/xmlrpc`, `/xmlrpc/2`, `/jsonrpc` are scheduled for removal; use JSON-2 for new integrations when suitable. This notice explicitly excludes custom `@route(type='jsonrpc')` controllers. Do not bake a mutable removal date into core rules. | [External RPC](https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html) |
| Python | Odoo 19 docs require Python >=3.10; installer tooling here separately needs Python >=3.11 for tomllib. Use the installed project's venv. | [Source install](https://www.odoo.com/documentation/19.0/administration/on_premise/source.html) |

## Corrections to Source Session Notes

- A universal ban on Settings `<block groups=...>` is incorrect: the official
  view reference documents `groups` on blocks. Investigate XML IDs, inheritance
  and effective group membership for the observed stripping bug.
- `@import url(...)` always breaking libsass is not established by Odoo docs.
  Keep the historical failure as a regression case; prefer local font assets,
  inspect compilation/network failures, and do not treat all CSS URL imports as invalid.
- Bulk results via `ir.actions.client` plus Owl Dialog are an existing module's
  UX choice, not a universal Odoo 19 prohibition on TransientModel wizards.
- Nullable Owl props and search-view attributes must follow the installed
  component/schema. The `ab_core_ui` session fix is not a rule to remove every
  `export {}` or every group attribute throughout the repository.
- `19.0.1.0.0` is the project's manifest version convention, not a known bug.
- Underscore-only custom model names are a project convention; native Odoo uses
  dotted names. Do not rename existing models as a compatibility cleanup.
