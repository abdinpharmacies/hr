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

## Pharmacy ERP Data Protection Rules

### Rule #1

No operation may risk inventory corruption, pricing corruption, or branch data leakage.

When uncertain, preserve data and reject destructive changes. For a pharmacy chain, inventory integrity is usually the single most important technical rule; wrong stock quantities replicated across branches can be more expensive than an obvious table failure.

### Critical Business Data

The following records must never be physically deleted:

- Products
- Product Categories
- Suppliers
- Purchase Orders
- Sales Orders
- Inventory Adjustments
- Inventory Transfers
- Stock Recycling Records
- Contracts
- Price Lists
- Branches
- Warehouses

Use:

```python
active = fields.Boolean(default=True)
```

instead of deletion whenever possible.

### Inventory Protection Rules

Agents must never directly modify computed or system-managed inventory quantities:

- `qty_available`
- `virtual_available`
- `free_qty`
- `incoming_qty`
- `outgoing_qty`

Forbidden:

```python
product.qty_available = 100
```

Inventory changes must occur through:

- Stock Move
- Inventory Adjustment
- Transfer
- Receipt
- Internal Transfer
- Approved Stock Recycling Process

Direct quantity edits are one of the most common causes of corrupted stock in pharmacy systems.

### External Database Integration Rules

External databases, including B-Connect and SQL integration sources, are **read-only** unless explicitly stated otherwise.

Agents must:

- Read from B-Connect or external SQL sources.
- Process and validate inside Odoo.
- Store business operations inside Odoo PostgreSQL.

Agents must not run external database writes such as:

```sql
UPDATE BConnect_Table ...
DELETE FROM BConnect_Table ...
TRUNCATE BConnect_Table ...
```

without explicit approval.

### Replication Safety Rules

Use an integration queue pattern:

```text
External DB
  -> Import Queue
  -> Validation
  -> Odoo Business Logic
  -> Final Records
```

Avoid direct writes:

```text
External DB
  -> Direct Write
  -> Production Tables
```

Queue-based imports make troubleshooting and recovery much safer.

### Product Master Protection

After product creation, the following fields should not be editable by normal users:

- Product Code
- Barcode
- External Reference

Only Inventory Manager or System Administrator users should be able to modify them. This prevents inventory mismatches across branches and external systems.

### Branch Security Rules

Users assigned to a branch can view their branch data only.

They cannot view other branches unless they belong to an authorized higher-level group, such as:

- Manager
- Regional Manager
- Administrator

See the detailed inherited-admin guard rule in Development Rules before implementing branch restrictions.

### Pricing Protection

Every price modification should log:

- `old_price`
- `new_price`
- `changed_by`
- `change_date`

Prefer creating a dedicated history model such as `ab_product_price_history` instead of overwriting prices without traceability.

### PostgreSQL Backup Rules

Recommended pharmacy production backup retention:

- Hourly: 72 backups
- Daily: 60 backups
- Weekly: 24 backups
- Monthly: 24 backups

Inventory and pricing mistakes may only be discovered several weeks later.

Create a dedicated PostgreSQL backup before:

- Mass Price Update
- Mass Product Import
- Mass Barcode Update
- Inventory Adjustment Import
- Stock Recycling Batch
- Supplier Synchronization

Example:

```bash
pg_dump \
  -U odoo19 \
  -F c \
  -d abdin_prod \
  -f before_mass_import_$(date +%F_%H-%M).backup
```

### Odoo Upgrade Rules

Never run this during normal module development:

```bash
-u base
```

Use targeted upgrades only:

```bash
-u ab_stock_recycling
-u module1,module2
```

Reason: `-u base` validates every view and inherited XML across the database and can expose unrelated issues during a focused module change.

### Git Rules For Hotfix Transfers

Before cherry-picking between branches such as `dev`, `ab_stock_recycling`, `ab_quality_assurance`, and `ab_orders_management`:

```bash
git log --oneline branch_name
```

Identify exact commits and prefer:

```bash
git cherry-pick <commit_hash>
```

Avoid merging a whole feature branch for hotfix transfers unless explicitly requested. This keeps module histories isolated.

### Translation Rules

For translation files such as `ar.po` and `ar_001.po`, agents must:

- Preserve existing `msgid` values.
- Append translations when needed.
- Avoid mass regeneration.
- Never delete `ar.po` or `ar_001.po` during upgrades.

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

6. **Avoid hard model dependencies in field declarations.**

   A `Many2one`, `One2many`, or `Many2many` field to a model from another module creates a **registry-level dependency** — Odoo must resolve that model at module load time. If the external module is missing, the entire module crashes on install/upgrade.

   **Preferred approach:** Use Python-level validation at runtime instead of a database field + record rule.

   ```python
   # ❌ Avoid — creates hard schema dependency
   class ResUsers(models.Model):
       _inherit = 'res.users'
       branch_store_id = fields.Many2one('external_module.model')

   # record rule referencing user.branch_store_id.id

   # ✅ Better — validate at runtime, no schema coupling
   class MyModel(models.Model):
       def _get_user_store(self, user):
           return self.env['external_module.model'].search([...], limit=1)

       @api.constrains('store_ids')
       def _check_user_store(self):
           for rec in self:
               store = rec._get_user_store(self.env.user)
               if store and rec.store_ids != store:
                   raise ValidationError(_("..."))
   ```

   This way the module installs cleanly even when the external module is absent, and the external model is only queried at runtime (where failures are handled gracefully).

7. **Guard branch/restricted group logic against inherited admin access.**

   When you modify `base.group_system` via `implied_ids` to include your module's groups, every system (Settings/Admin) user automatically inherits **all groups in the chain**. This means `has_group('your_module.branch_role')` returns `True` for admin even though admin has no department/branch configured.

   **Always check the highest privilege group first** before applying branch-level restrictions. If the user has the manager or admin group, skip the branch role check entirely.

   ```python
   # ❌ Bad — admin inherits branch_role via implied_ids chain and hits the validation
   def btn_get_overstock_for_stores(self):
       if self.env.user.has_group('ab_stock_recycling.group_ab_stock_recycling_branch_role'):
           branch_store = self._get_branch_store_for_user(self.env.user)
           if not branch_store:
               raise ValidationError(_("User has 'Branch Role' but not linked to department"))

   # ✅ Better — check highest group first, branch logic only for non-admin users
   def btn_get_overstock_for_stores(self):
       if self.env.user.has_group('ab_stock_recycling.group_ab_stock_recycling_manager'):
           pass  # managers/admins bypass branch store restriction
       elif self.env.user.has_group('ab_stock_recycling.group_ab_stock_recycling_branch_role'):
           branch_store = self._get_branch_store_for_user(self.env.user)
           if not branch_store:
               raise ValidationError(_("User has 'Branch Role' but not linked to department"))
   ```

   The same pattern applies to `_default_overstock_store_ids` or any default/get method that returns branch-scoped values. Always let admin/managers fall through to the unrestricted path.

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

### Critical Odoo 19 Learnings
- **OWL template operators**: Use JavaScript operators (`&&`, `||`, `!`) with XML entity escaping (`&amp;` for `&`). Do NOT use QWeb-style `and`/`or`/`not` — OWL's expression parser treats those as property access (`ctx['not']`), breaking logic.
- **SCSS `@import url()`**: Odoo 19's libsass cannot fetch external URLs (e.g. Google Fonts). Any `@import url(...)` silently breaks the entire `web.assets_backend` bundle, causing blank/HTML-rendered screens. Use font-face declarations as CSS hints or inline fonts.
- **Bulk code results**: Use `ir.actions.client` + OWL Dialog (not `ValidationError` popup or `TransientModel` wizard form) for modern UX.

## Phase 0 Findings — `ab_product_seo`

These facts were measured during the SEO discovery phase for the future `ab_product_seo` module. Use them as the baseline for architecture and implementation decisions.

### Strategic Conclusion

Ready API is no longer the primary value source. E-Plus/B-Connect already contains enough structured pharmaceutical data to build a professional internal SEO platform.

First business value is not AI, Ready API, or RAG. First business value is:

- Populate native Odoo SEO fields correctly.
- Govern review and approval of pharmacy SEO content.
- Publish approved Arabic and English SEO content safely.

### Odoo Product and Website Metrics

| Metric | Count |
|--------|------:|
| `product.template` total | 110 |
| Linked to `ab_product` | 25 |
| Published website products | 106 |
| Active + saleable templates | 107 |
| Meta title filled | 0 |
| Meta description filled | 0 |
| Ecommerce description filled | 24 |
| Website description filled | 24 |
| Product images in Odoo | 1 |
| SEO optimized products | 0 |

SEO coverage is effectively zero for native meta fields. Image coverage is also a major issue and should be handled before heavy AI investment.

### `ab_product` Metrics

| Metric | Count |
|--------|------:|
| `ab_product` total | 102,834 |
| Active + saleable | 30,420 |
| With product code | 102,834 |
| With `eplus_serial` | 102,833 |
| Barcode rows | 10,000 |
| Products linked to barcode | 4,025 |
| With effective material | 7,485 |
| With description | 38,280 |
| With scientific group | 1 |

Identifier matching is strong by product code and `eplus_serial`; barcode coverage is useful but not enough as the primary key.

### Installed Languages

Installed languages:

- `ar_001`
- `en_US`

Arabic and English must be supported from day one.

### E-Plus `Item_Catalog` Findings

`Item_Catalog` contains 103,846 rows and 77 columns.

Useful fields discovered:

- `itm_code`
- `itm_name_ar_encrypt`
- `itm_name_en_encrypt`
- `com_id`
- `itm_com_code`
- `itm_ismedicine`
- `itm_scientific_n1`
- `itm_scientific_n2`
- `itm_scientific_group_id`
- `itm_usage_manner_id`
- `itm_effictive`
- `itm_effictive_perc`
- `itm_g1`
- `itm_g2`
- `itm_g3`
- `itm_origin`
- `itm_notes`
- `itm_image`

Coverage highlights:

| E-Plus Field | Count |
|--------------|------:|
| Product code | 103,846 |
| Plain Arabic name | 0 |
| Plain English name | 0 |
| Encrypted Arabic name | 103,846 |
| Encrypted English name | 103,843 |
| Manufacturer/company id | 103,794 |
| Group 1 | 73,918 |
| Group 2 | 73,697 |
| Group 3 | 68,976 |
| Scientific name 1 | 89,848 |
| Scientific group id | 65,370 |
| Usage manner id | 58,251 |
| Effective material | 7,509 |
| Notes | 38,280 |
| Origin | 103,846 |
| Image | 0 |

Important: plain Arabic and English name columns are empty. Product names appear to be stored in encrypted columns. Do not assume plain name columns are usable without confirming decryption logic.

### Useful E-Plus Lookup Tables

The following lookup tables exist and should be considered internal SEO data sources before using external APIs:

- `Company`
- `Groups`
- `Scientific_Groups`
- `item_usage_manner`
- `Usage_Causes`
- `Item_Usage_Causes`
- `Item_Origins`

### Existing Ecommerce Boundary

`ab_website_sale_product` already synchronizes `ab_product` into native `product.template`.

It already owns:

- Product template creation and update.
- Product name and code sync.
- Price and cost sync.
- Sale/purchase flags.
- Active state.
- `description`
- `description_sale`
- `description_ecommerce`
- `website_description`
- `is_published`
- Public categories.
- Product tags.
- Images.
- E-Plus stock snapshots.

`ab_product_seo` must not duplicate this functionality. It should govern approved SEO content and publish into native Odoo fields after review.

### Native Odoo SEO Fields

Odoo 19 already provides:

- `website_meta_title`
- `website_meta_description`
- `website_meta_keywords`
- `website_meta_og_img`
- `seo_name`
- `description_ecommerce`

Odoo already handles:

- Canonical URLs.
- OpenGraph.
- Twitter cards.
- `hreflang`.
- Sitemap.
- Product JSON-LD.
- Breadcrumb JSON-LD.

The SEO module must populate and govern these fields, not replace Odoo website SEO rendering.

### `ab_product_seo` Ownership Rules

`ab_product_seo` owns:

- SEO content lifecycle.
- SEO drafts.
- Arabic and English SEO content.
- Review workflow.
- Approval workflow.
- Publishing decisions.
- Versioning.
- Rollback.
- SEO publish logs.
- SEO audit logs.
- Enrichment tracking.
- Future AI/RAG readiness.

`ab_product_seo` does not own:

- Product master data.
- Stock quantities.
- Pricing.
- E-Plus synchronization.
- Website product synchronization.
- Product image synchronization.
- Automatic publishing of medical content.

### Required Workflow

Use this lifecycle:

```text
draft
-> generated
-> under_review
-> approved
-> published
-> rejected
-> archived
```

Generated pharmacy content must remain reviewable. No medical claims may be auto-published.

### Recommended Roadmap

Phase 1: `ab_product_seo` core framework only.

- Models.
- SEO records.
- SEO translations.
- SEO versions.
- SEO publish logs.
- SEO audit logs.
- Review workflow.
- Approval workflow.
- Publishing into native Odoo SEO fields.

Phase 2: internal SEO generator.

- Generate SEO drafts from internal product/E-Plus data:
  - Product name.
  - Scientific name.
  - Manufacturer.
  - Origin.
  - Usage.
  - Product group.
  - Notes.

Phase 3: Arabic SEO.

- Arabic meta title.
- Arabic meta description.
- Arabic short description.
- Arabic FAQ.
- Arabic public description.

Phase 4: queue architecture.

Use `queue_job` / `integration_queue_job`.

Pipeline:

```text
Snapshot
-> Generate
-> Review
-> Publish
```

Recommended batch size:

```text
100 products/job
```

Recommended identity key:

```text
seo_product_<product_id>_<lang>
```

Phase 5: Ready API pilot only.

- Test 100 products.
- Measure match rate.
- Measure data quality.
- Measure Arabic quality.
- Measure scientific data quality.
- Keep Ready API only if it provides better enrichment than E-Plus.

### Ready API Rules

Ready API is optional enrichment only.

Free plan constraints:

- 300 requests/day.
- 7-day trial.
- Localhost-only test key.

Ready API must be:

- Cached.
- Rate limited.
- Queue driven.
- Manually controlled.
- Never the source of truth.
- Never called during website page load.
- Never used for automatic full-catalog publishing.

### Matching Priority

Use this order for enrichment/matching:

1. Barcode.
2. `eplus_serial`.
3. Product code.
4. Scientific grouping.
5. Normalized product name.
6. Fuzzy match.

### Future RAG Direction

The product catalog is a strong future knowledge base because it contains 102,834 products and large coverage for scientific names, manufacturers, categories, origins, and notes.

Future architecture:

```text
ab_product
  -> ab_product_seo
  -> approved SEO content
  -> embedding pipeline
  -> pgvector
  -> pharmacy AI assistant
```

Only approved public content should be embedded for customer-facing RAG. Separate retrieval-safe fields from non-public medical/internal fields.

### Architecture-Only Prompt Guardrail

Before implementing `ab_product_seo`, ask for an architecture document only. The prompt must include:

- Do not write code.
- Do not modify files.
- Do not create commits.
- Return architecture only.
- Use Phase 0 metrics as facts.
- Follow AGENTS.md exactly.
- Design governance-first architecture.
- Use native Odoo SEO field publishing.
- Support Arabic + English.
- Include queue-based generation.
- Include versioning and rollback.
- Include audit trail.
- Keep Ready API optional.
- Include future pgvector/RAG compatibility.
- Stay compatible with `ab_website_sale_product`.
- Do not directly modify source product data.

## Session Summary — ab_self_inventory SaaS UI Redesign

### Completed
- **List view card rows**: White bg, rounded corners, shadow hover, left accent border (`self_inventory.scss`).
- **Premium state badges**: Gradient + glow (`.ab_state_badge`).
- **Deadline color coding**: Green/orange/red/past urgency with icon + relative text (`.ab_deadline_widget`).
- **Quick actions dropdown**: "..." button on row hover with Open/Edit/Duplicate (`.ab_quick_actions_menu`).
- **Branch popover tooltip**: Body-level DOM append, sync `getBoundingClientRect()` before await, absolute positioning with scrollX/Y.
- **Kanban views**: Created for all 3 models (batch/request/process) with KPI row, branch pill, deadline, requester meta, grouped by state (`self_inventory_kanban_views.xml`).
- **Form redesign**: Hero card, KPI cards row (4-column grid with top accent), two-column layout (1fr 340px sidebar), branch chips, progress SVG circle, state-based timeline, sidebar info cards (`self_inventory_form.scss`, `self_inventory_form_widgets.js`).
- **5 form OWL widgets**: FormHeroWidget, KpiCardWidget (with shortage/extra types), BranchFormWidget, FormProgressWidget, TimelineWidget.
- **6 list/kanban OWL widgets**: BranchPillsWidget (body-level popover), KpiWidget, StateBadgeWidget, RowTitleWidget (with quick actions), DeadlineWidget, BranchDialog.
- **Bulk product codes OWL Dialog**: Replaced old `TransientModel` wizard form with `BulkImportResultsDialog` — summary cards (branches processed / added / missing), branch table, expandable missing-codes section, "Download Missing Codes" button, empty state. Triggered via `ir.actions.client` with tag `ab_inventory_bulk_code_results`.
- **Dead code removal**: Removed `SelfInventoryBatchCodeResultWizard`, `SelfInventoryBatchCodeResultLine` transient models, their form view in batch views XML, and their 4 access lines from `ir.model.access.csv`.
- **Test updated**: `test_batch_add_product_codes` now asserts `ir.actions.client` params instead of wizard `res_model/res_id`.

### Key Files
| File | Purpose |
|---|---|
| `ab_self_inventory/static/src/scss/self_inventory.scss` | List/kanban SCSS |
| `ab_self_inventory/static/src/scss/self_inventory_form.scss` | Form SCSS + bulk dialog SCSS |
| `ab_self_inventory/static/src/js/self_inventory_widgets.js` | 6 list/kanban widgets |
| `ab_self_inventory/static/src/js/self_inventory_form_widgets.js` | 5 form widgets |
| `ab_self_inventory/static/src/js/self_inventory_bulk_code_dialog.js` | BulkImportResultsDialog + client action handler (NEW) |
| `ab_self_inventory/models/self_inventory_request.py` | `_get_bulk_code_result_action()` replaces wizard open; removed wizard models |
| `ab_self_inventory/views/self_inventory_kanban_views.xml` | Kanban views |
| `ab_self_inventory/views/self_inventory_request_batch_views.xml` | Batch list + form; removed wizard form view |
| `ab_self_inventory/views/self_inventory_request_views.xml` | Request list + form |
| `ab_self_inventory/views/self_inventory_process_views.xml` | Process list + form |
| `ab_self_inventory/security/ir.model.access.csv` | Removed 4 wizard access lines |
| `ab_self_inventory/__manifest__.py` | Asset registration (added bulk_code_dialog.js) |
| `ab_self_inventory/tests/test_self_inventory.py` | Updated assertions for client action |

### Key Decisions
- Popover DOM appended to `document.body` (not nested inside widget) to avoid ancestor CSS `transform`/`will-change` clipping.
- `getBoundingClientRect()` captured synchronously before `await` in `onEnter()` to avoid zero-rect from virtual-scrolling detach.
- Form widgets access sibling fields via `this.props.record.data.fieldName` — handle both raw values and Many2one arrays.
- ProgressWidget computes `percent = Math.round((processed / requested) * 100)` with safe division-by-zero.
- TimelineWidget generates items from record state/dates via static `timelineMap` — no separate history model required.
- **OWL template operators**: JavaScript operators (`!`, `&&`, `||`) with XML entity escaping (`&amp;` for `&`) — NOT QWeb-style `not`/`and`/`or`.
- **SCSS `@import url()` removed** from form SCSS to prevent libsass failure from breaking the entire backend asset bundle.
- **Bulk code results**: `ir.actions.client` → OWL Dialog (no TransientModel wizard, no ValidationError).
- **Dialog "Download Missing Codes"** uses client-side Blob + anchor download (no server round trip).
