# Historical Repository and Compatibility Notes

Read only when investigating these named modules or earlier regressions. This is
an undated source snapshot, not a fresh audit, upgrade plan or executable recipe.
Module statuses, file line numbers and completion claims must be rechecked.
The quoted claims about the JS loader, Owl aliases, CSS imports and bulk dialogs
are superseded by the [verified compatibility matrix](compatibility.md).
Do not replay broad rewrites or treat the old version-format observation as a bug.

Search within the excerpt for `Modules Needing Attention`, `Additional Reference
Modules`, `_sql_constraints`, `odoo.define`, `self._cr` or `Critical Odoo 19 Learnings`.

Source: original AGENTS.md lines 1046-1164.

<!-- source-excerpt:1046-1164 -->
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
- Developer: '<current git user>',.
- Template: `ab_template` structure.
- Data order: `security/security_groups.xml` -> `security/record_rules.xml` -> `security/ir.model.access.csv` -> `views/menus.xml` -> views.
- Focus: start with critical issues first.

### Critical Odoo 19 Learnings
- **OWL template operators**: Use JavaScript operators (`&&`, `||`, `!`) with XML entity escaping (`&amp;` for `&`). Do NOT use QWeb-style `and`/`or`/`not` — OWL's expression parser treats those as property access (`ctx['not']`), breaking logic.
- **SCSS `@import url()`**: Odoo 19's libsass cannot fetch external URLs (e.g. Google Fonts). Any `@import url(...)` silently breaks the entire `web.assets_backend` bundle, causing blank/HTML-rendered screens. Use font-face declarations as CSS hints or inline fonts.
- **Bulk code results**: Use `ir.actions.client` + OWL Dialog (not `ValidationError` popup or `TransientModel` wizard form) for modern UX.
<!-- end-source-excerpt -->
