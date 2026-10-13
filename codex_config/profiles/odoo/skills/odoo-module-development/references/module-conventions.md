# Scaffold and Load Order

The following project conventions come from AGENTS.md. Use the actual local ab_template, adding only required files. The manifest ordering is a starting pattern: actual references take precedence (define actions before menus that reference them). Inherit existing views; new models can require new root views. New developer metadata is a dictionary entry (`developer` string from git user.name), not a Python assignment. Do not add groups from Python. Keep tests in development/CI but omit them from the final runtime artifact. See the compatibility matrix for verified version claims.

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
└── static/
    └── description/
        └── icon.png
```

Template rules:

- Create only the files and folders the module actually needs.
- Use `data/` only for required runtime records such as sequences or defaults.
- Do not create `demo/` files.
- Keep production addon packages runtime-only. Do not ship `tests/`, test fixtures, migration folders for development databases, or generated `__pycache__` files.
- Keep the module aligned with the provided template and avoid extra scaffolding.

Manifest example:

```python
{
    'name': 'ab_template',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': '<module category>',
    'author': 'Abdin Pharmacies',
    'developer': '<current git user>',
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
- Every Python file in a module `models/` folder must be imported from that module's `models/__init__.py`.
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
- **Order data records by dependency.** Within a single XML file, a record referenced by `ref()` in an `eval` attribute must be defined before the record that references it. Otherwise fresh install fails with `External ID not found` because Odoo processes the file sequentially.

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

