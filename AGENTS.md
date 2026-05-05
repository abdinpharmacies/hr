# AGENTS.md - Odoo 19.0 Custom Addons Development Guide

Single source of truth for custom addons development in `/opt/odoo19/custom-addons`.

Scope:

- Backend Python ORM
- XML views, actions, menus, security, and data
- JS and assets only when the module truly needs them
- Testing and module packaging

Module creation rules:

- Follow the provided `ab_template` scaffold unless the module goal clearly requires extra files.
- Do not create demo data files for any module or test model.
- Do not add unnecessary database edits, cron jobs, hooks, triggers, or direct SQL.
- Do not use `env.ref()` to create records in other modules.
- Do not edit shared frontend components in a way that can affect other modules.
- If frontend work is required, create new module-scoped classes, components, or templates and connect them only to the working module.
- Keep the module self-contained and limit changes to the module being developed.
- Use module technical names with underscores `_`, not dots `.`.
- All new modules use `author = "Alhassan Hossny"`.

## Odoo 19 Compatibility Notes

### Views

- List views use `<list>` instead of `<tree>`.
- `view_mode` must use `list`, not `tree`.
- Kanban templates use `<t t-name="card">`, not `kanban-box`.
- `attrs` and `states` are rejected in 19.0.
- Use Python boolean expressions in XML instead.

Example:

```xml
<field name="field_b" invisible="field_a == 4"/>
```

### JavaScript and Assets

- Legacy `odoo.define(...)` is deprecated.
- Use ES modules with `/** @odoo-module **/`.
- Register assets in `__manifest__.py`.
- Do not add new `assets.xml` files.

Example:

```javascript
/** @odoo-module **/
import { ... } from "@web/...";
```

### Constraints

- Use `models.Constraint` instead of `_sql_constraints`.

Example:

```python
_uniq_name = models.Constraint(
    'UNIQUE(name)',
    'Name must be unique.',
)
```

### Domains

- Use `fields.Domain` for new code.
- `fields.Domain.OR(...)` returns a Domain object, not a list.
- For XML-RPC, convert the domain to a list when needed.
- Avoid uppercase domain operators, `<>`, `==`, raw `SQL(...)`, and `group_operator`.

Example:

```python
from odoo import fields

domain = fields.Domain('name', '=', 'abc') | fields.Domain('phone', 'ilike', '7620')
```

## Development Rules

1. Python models and logic first.
2. Security next.
3. XML views, actions, and menus next.
4. Data only when required.
5. Tests last.

## Repository and Environment

Addon structure:

```text
addon_name/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── [model_files].py
├── views/
│   └── [view_files].xml
├── security/
│   ├── security_groups.xml
│   ├── record_rules.xml
│   └── ir.model.access.csv
├── data/                # optional, non-demo runtime data only
├── wizard/              # optional
├── report/              # optional
├── tests/
└── static/
    └── description/
        └── icon.png
```

Template rules:

- Create only the files and folders the module actually needs.
- Use `data/` only for required runtime records such as sequences or defaults.
- Do not create `demo/` files.
- Keep the module aligned with the provided template and avoid extra scaffolding.

Manifest example:

```python
{
    'name': 'ab_template',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Alhassan Hossny',
    'application': True,
    'depends': ['base'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
    ],
    'installable': True,
}
```

Python:

- Python 3.10 or newer.
- Use virtual environments.
- Always use recordsets.
- Avoid per-record queries.
- Use `mapped()`, `filtered()`, and `sorted()` on recordsets.

Method overrides:

- Must support multi-recordsets.
- Must call `super()`.
- No side effects in loops.

Forbidden APIs:

- `odoo.osv`
- `record._cr`
- `record._uid`
- `record._context`

Required:

- `record.env.cr`
- `record.env.uid`
- `record.env.context`

## XML Rules

- All UI must be defined in XML.
- Always use view inheritance.
- Avoid positional XPath.
- Use stable anchors.

## Security

Every model must have:

- `ir.model.access.csv`
- Record rules if applicable
- Correct group usage

Security layer order:

1. `ir.module.category`
2. `res.groups.privilege`
3. `res.groups`

Example:

```xml
<record id="module_category_xxx" model="ir.module.category">
    <field name="name">Module Name</field>
</record>

<record id="privilege_xxx_access" model="res.groups.privilege">
    <field name="name">Access</field>
    <field name="category_id" ref="module_category_xxx"/>
</record>

<record id="group_xxx_user" model="res.groups">
    <field name="name">Users</field>
    <field name="privilege_id" ref="privilege_xxx_access"/>
</record>
```

## Manifest Load Order

Use this order for new modules:

- `security/security_groups.xml`
- `security/record_rules.xml`
- `security/ir.model.access.csv`
- `views/menus.xml`
- required non-demo `data/*.xml`
- `views/*.xml`
- `wizard/*.xml`
- `report/*.xml`

## External APIs

- Legacy XML-RPC and JSON-RPC are deprecated.
- Do not build new features around them.

## Testing

Minimum:

- One business rule test.
- One access or record rule test if applicable.

## Upgrade Safety

Code must:

- Survive 19.x upgrades.
- Avoid monkey patching.
- Avoid full JS overrides.
- Use XML IDs only.

## AI Agent Rules

Agents must:

- Not refactor unrelated files.
- Not rename XML IDs unless instructed.
- Make the smallest valid diff.
- Reject deprecated APIs.

## Repository Snapshot

### Modules Needing Attention

| Module | Status | Notes |
|--------|--------|-------|
| ab_contract | Needs review | `_sql_constraints` issues |
| ab_costcenter | Needs review | Legacy JS detected |
| ab_hr_org_chart | Needs review | Legacy JS: `odoo.define` |
| ab_inventory | Needs review | Uses `self._cr` |
| ab_inventory_adjust | Needs review | Legacy JS and `self._cr` |
| ab_sales | Needs review | Uses `self._cr` |
| ab_sales_contract | Critical | Uses `_sql_constraints` |
| ab_transfer | Needs review | Uses `self._cr` |
| ab_whatsapp_api | Needs review | Uses `self._cr` |
| abdin_js | Critical | Legacy `odoo.define` in many files |
| payroll_test | Critical | Uses `_sql_constraints` |

### Additional Reference Modules

| Module | Status | Notes |
|--------|--------|-------|
| ab_telegram_webhook | Ready | |
| muk_web_appsbar | Ready | |
| muk_web_chatter | Ready | |
| muk_web_colors | Ready | |
| muk_web_dialog | Ready | |
| muk_web_group | Ready | |
| muk_web_refresh | Ready | |
| muk_web_theme | Ready | |
| queue_job | Ready | |
| integration_queue_job | Ready | |
| auto_backup | Ready | |
| auto_logout_idle_user_odoo | Ready | |
| auth_session_timeout | Ready | |
| hr_employee_permissions | Ready | |

## Odoo 19 Compatibility Issues

### Critical: `_sql_constraints`

Odoo 19 requires `models.Constraint` instead of `_sql_constraints`.

| Module | File | Issue |
|--------|------|-------|
| ab_sales_contract | `models/ab_contract_product_origin.py` | Line 12: `_sql_constraints` |
| payroll_test | `models/payroll_rule.py` | Line 38: `_sql_constraints` |

Fix:

```python
# Old
_sql_constraints = [
    ('unique_name', 'unique(name)', 'Name must be unique.'),
]

# New
_uniq_name = models.Constraint(
    'UNIQUE(name)',
    'Name must be unique.',
)
```

### High: Legacy JavaScript (`odoo.define`)

These files use the deprecated AMD-style loader and should be moved to ES modules.

- `abdin_js/static/src/js/xxx_form_edit_on_click.js`
- `abdin_js/static/src/js/xxx_html_table_sort_js_pure.js`
- `abdin_js/static/src/js/xxx_html_table_sort_working.js`
- `abdin_js/static/src/js/xxx_web_refresher.js`
- `abdin_js/static/src/js/urgent_save_firefox_fix.js`
- `abdin_js/static/src/js/xxx_save_record_auto.js`
- `abdin_js/static/src/js/xxx_one2many_widget_autosave.js`
- `abdin_js/static/src/js/list_view.js`
- `abdin_js/static/src/js/html_table_sort.js`
- `abdin_js/static/src/js/add_equal_ilike_to_filter_menu.js`
- `abdin_js/static/src/js/eastern_to_western_numbers.js`
- `abdin_js/static/src/js/abdin_date_widget.js`
- `abdin_js/static/src/js/fix_tabindex_in_odoo_15.js`
- `ab_inventory_adjust/static/src/js/helper_functions.js`
- `ab_inventory_adjust/static/src/js/odoo_barcode_one2many.js`
- `ab_inventory_adjust/static/src/js/get_inventory_details.js`
- `ab_inventory_adjust/static/src/js/barcode_list_view.js`
- `ab_inventory_adjust/static/src/js/odoo_barcode_one2many_try1.js`
- `ab_inventory_adjust/static/src/js/override_enter_key_abstract_field.js`
- `ab_hr_org_chart/static/src/js/hr_org_chart.js`
- `ab_costcenter/static/src/js/archive_security.js`

### Medium: Direct Cursor Access (`self._cr`)

These modules still use `self._cr` and should be moved to `self.env.cr`.

| Module | File | Lines |
|--------|------|-------|
| ab_transfer | `models/transfer_line.py` | 90, 98, 111, 117 |
| ab_inventory | `models/ab_product_source_pending.py` | 42 |
| ab_inventory_adjust | `models/ab_inventory_adjust_header_push.py` | 132 |
| ab_sales | `models/ab_sales_ui_api_replication_inherit.py` | 92 |
| ab_whatsapp_api | `models/whatsapp_service.py` | 1063, 1125, 1216, 1282, 1457 |
| auto_backup | `models/db_backup.py` | 30 |

### Low: Manifest Version Format

Most modules use `19.0.1.0.0` instead of `19.0`. This is cosmetic, not a functional error.

### Session Notes

- Target: Odoo 19.0.
- Author: Alhassan Hossny.
- Template: `ab_template` structure.
- Data order: `security/security_groups.xml` -> `security/record_rules.xml` -> `security/ir.model.access.csv` -> `views/menus.xml` -> views.
- Focus: start with critical issues first.
