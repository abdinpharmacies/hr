# OpenCode Agent Reference - Odoo 19 Development

## Overview

This document serves as a general reference for all custom-addons modules in the Odoo 19 development environment.

---

## Module Inventory

### Core Business Modules (ab_*)

| Module | Status | Notes |
|--------|--------|-------|
| ab_announcement | Ready | |
| ab_base_models_inherit | Ready | Base inheritance module |
| ab_cities | Ready | |
| ab_contract | Needs review | Has `_sql_constraints` issues |
| ab_costcenter | Needs review | Legacy JS detected |
| ab_customer | Ready | |
| ab_data_from_excel | Ready | Excel import functionality |
| ab_distribution_store | Ready | |
| ab_eplus_collect_customers | Ready | |
| ab_eplus_connect | Ready | |
| ab_eplus_replication_contract | Ready | |
| ab_employee_tools | Ready | |
| ab_hr | Ready | Core HR module |
| ab_hr_applicant | Ready | |
| ab_hr_effects | Ready | |
| ab_hr_org_chart | Needs review | Legacy JS: `odoo.define` |
| ab_inventory | Needs review | Uses `self._cr` |
| ab_inventory_adjust | Needs review | Legacy JS, uses `self._cr` |
| ab_odoo_connect | Ready | |
| ab_odoo_replication | Ready | |
| ab_odoo_replication_upload | Ready | |
| ab_odoo_update | Ready | |
| ab_orders_management | Ready | |
| ab_pos | Ready | |
| ab_product | Ready | |
| ab_product_source | Ready | |
| ab_promo_program | Ready | |
| ab_quality_assurance | Ready | |
| ab_quality_assurance_ux | Ready | |
| ab_request_management | Ready | |
| ab_sales | Needs review | Uses `self._cr` |
| ab_sales_cashier | Ready | |
| ab_sales_contract | **CRITICAL** | Uses `_sql_constraints` |
| ab_sales_models_replication | Ready | |
| ab_sales_promo | Ready | |
| ab_smart_security_manager | Ready | |
| ab_store | Ready | |
| ab_supplier | Ready | |
| ab_template | Ready | |
| ab_transfer | Needs review | Uses `self._cr` |
| ab_user_extra | Ready | |
| ab_visit_report | Ready | |
| ab_wan | Ready | |
| ab_website | Ready | |

### Infrastructure/Utility Modules

| Module | Status | Notes |
|--------|--------|-------|
| abdin_css | Ready | |
| abdin_disable_text_wrap | Ready | |
| abdin_et | Ready | |
| abdin_js | **CRITICAL** | 14 files use legacy `odoo.define` |
| abdin_telegram | Ready | |
| ab_widgets | Ready | |
| ab_whatsapp_api | Needs review | Uses `self._cr` |
| ab_telegram_webhook | Ready | |

### Third-Party / Muk Modules

| Module | Status | Notes |
|--------|--------|-------|
| muk_web_appsbar | Ready | |
| muk_web_chatter | Ready | |
| muk_web_colors | Ready | |
| muk_web_dialog | Ready | |
| muk_web_group | Ready | |
| muk_web_refresh | Ready | |
| muk_web_theme | Ready | |

### Queue Job Modules

| Module | Status | Notes |
|--------|--------|-------|
| queue_job | Ready | |
| integration_queue_job | Ready | |

### Other Modules

| Module | Status | Notes |
|--------|--------|-------|
| auto_backup | Ready | |
| auto_logout_idle_user_odoo | Ready | |
| auth_session_timeout | Ready | |
| hr_employee_permissions | Ready | |
| payroll_test | **CRITICAL** | Uses `_sql_constraints` |

---

## Odoo 19 Compatibility Issues

### CRITICAL: _sql_constraints (Must Fix)

Odoo 19 requires `models.Constraint` instead of `_sql_constraints`.

| Module | File | Issue |
|--------|------|-------|
| ab_sales_contract | models/ab_contract_product_origin.py | Line 12: `_sql_constraints` |
| payroll_test | models/payroll_rule.py | Line 38: `_sql_constraints` |

**Fix Required:**
```python
# Odoo 17/18 (old)
_sql_constraints = [
    ('unique_name', 'unique(name)', 'Name must be unique.')
]

# Odoo 19 (new)
_uniq_name = models.Constraint(
    'UNIQUE(name)',
    'Name must be unique.',
)
```

### HIGH: Legacy JavaScript (odoo.define)

22 files use deprecated `odoo.define()`. Must convert to ES modules.

#### abdin_js (14 files - CRITICAL)
- static/src/js/xxx_form_edit_on_click.js
- static/src/js/xxx_html_table_sort_js_pure.js
- static/src/js/xxx_html_table_sort_working.js
- static/src/js/xxx_web_refresher.js
- static/src/js/urgent_save_firefox_fix.js
- static/src/js/xxx_save_record_auto.js
- static/src/js/xxx_one2many_widget_autosave.js
- static/src/js/list_view.js
- static/src/js/html_table_sort.js
- static/src/js/add_equal_ilike_to_filter_menu.js
- static/src/js/eastern_to_western_numbers.js
- static/src/js/abdin_date_widget.js
- static/src/js/fix_tabindex_in_odoo_15.js

#### ab_inventory_adjust (8 files)
- static/src/js/helper_functions.js
- static/src/js/odoo_barcode_one2many.js
- static/src/js/get_inventory_details.js
- static/src/js/barcode_list_view.js
- static/src/js/odoo_barcode_one2many_try1.js
- static/src/js/override_enter_key_abstract_field.js

#### Other modules
- ab_hr_org_chart/static/src/js/hr_org_chart.js
- ab_costcenter/static/src/js/archive_security.js

**Fix Required:**
```javascript
// Old (deprecated)
odoo.define('module.name', function (require) { ... });

// New (Odoo 17+)
/** @odoo-module **/
import { ... } from "@web/...";
```

### MEDIUM: Direct Cursor Access (self._cr)

These modules use `self._cr` which should be replaced with `self.env.cr`:

| Module | File | Lines |
|--------|------|-------|
| ab_transfer | models/transfer_line.py | 90, 98, 111, 117 |
| ab_inventory | models/ab_product_source_pending.py | 42 |
| ab_inventory_adjust | models/ab_inventory_adjust_header_push.py | 132 |
| ab_sales | models/ab_sales_ui_api_replication_inherit.py | 92 |
| ab_whatsapp_api | models/whatsapp_service.py | 1063, 1125, 1216, 1282, 1457 |
| auto_backup | models/db_backup.py | 30 |

**Fix Required:**
```python
# Old
self._cr.execute("SELECT ...")

# New
self.env.cr.execute("SELECT ...")
```

### LOW: Manifest Version Format

All modules use `'19.0.1.0.0'` instead of `'19.0'`. This is cosmetic but not an error.

---

## Odoo 19 Development Rules

### XML Views

- Use `<list>` instead of `<tree>` for list views
- Use `invisible="field_a == 4"` instead of `attrs="{'invisible': [...]}"`

### Python/ORM

- Use recordsets: `self.env['model'].search(...)`
- Use `mapped()`, `filtered()`, `sorted()` on recordsets
- Use `self.env.cr` instead of `self._cr`
- Use `self.env.uid` instead of `self._uid`
- Use `self.env.context` instead of `self._context`

### Constraints

```python
# Odoo 19 style
_uniq_name = models.Constraint(
    'UNIQUE(name)',
    'Name must be unique.',
)
```

### Domains

```python
# Odoo 19 style
from odoo import fields
domain = fields.Domain('name', '=', 'abc')
```

### JavaScript

```javascript
/** @odoo-module **/
import { ... } from "@web/...";
```

### Security (res.groups.privilege Layer)

```xml
<!-- 1. Category -->
<record id="module_category_xxx" model="ir.module.category">
    <field name="name">Module Name</field>
</record>

<!-- 2. Privilege -->
<record id="privilege_xxx_access" model="res.groups.privilege">
    <field name="name">Access</field>
    <field name="category_id" ref="module_category_xxx"/>
</record>

<!-- 3. Group -->
<record id="group_xxx_user" model="res.groups">
    <field name="name">Users</field>
    <field name="privilege_id" ref="privilege_xxx_access"/>
</record>
```

---

## Session Development Notes

- **Branch**: dev (main development branch)
- **Target**: Odoo 19.0
- **Focus**: Start with critical issues first (_sql_constraints, legacy JS)
