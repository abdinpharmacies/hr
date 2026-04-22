# OpenCode Agent Reference - ab_orders_management

## Module Overview
- **Module Name**: ab_orders_management
- **Version**: 19.0.1.0.0
- **Depends**: base, web, ab_hr

## Models (3 main models)

### 1. ab_pharmacy_delivery_branch
- **Model**: `ab_pharmacy_delivery_branch`
- **File**: `models/pharmacy_delivery_branch.py`
- **Fields**:
  - `name` (char, required)
  - `hr_department_id` (Many2one to ab_hr_department)
  - `user_ids` (Many2many res.users)
  - `pilot_ids` (One2many to ab_pharmacy_delivery_pilot)
  - `assignment_ids` (One2many to ab_pharmacy_delivery_assignment)
  - `pilot_count`, `assignment_count` (computed)
- **Constraints**: UNIQUE(name), UNIQUE(hr_department_id)

### 2. ab_pharmacy_delivery_pilot
- **Model**: `ab_pharmacy_delivery_pilot`
- **File**: `models/pharmacy_delivery_pilot.py`
- **Fields**:
  - `name` (char, required)
  - `pilot_code` (char)
  - `shift` (char)
  - `status` (selection: free, in_delivery)
  - `hr_employee_id` (Many2one to ab_hr_employee)
  - `hr_department_id` (Many2one to ab_hr_department)
  - `branch_id` (Many2one to ab_pharmacy_delivery_branch, required)
  - `sign_in_datetime`, `sign_in_date`, `sign_in_order` (datetime/date/int)
  - Count fields: delivery_assigned_count, delivery_completed_count, order_assigned_count, order_completed_count, handled_item_count
- **Constraints**: UNIQUE(name, branch_id), UNIQUE(hr_employee_id)
- **Key Methods**:
  - `action_sync_pilots_from_hr()` - Sync pilots from HR employees
  - `get_dashboard_payload()` - Get dashboard data
  - `action_start_delivery()`, `action_finish_delivery()`
  - `action_add_additional_assignment()` - Add additional order for pilot in delivery
  - `_sync_status_from_assignments()`
  - `_get_default_branch()` - Get default branch "فرع التلفزيون الاقصر"

### 3. ab_pharmacy_delivery_assignment
- **Model**: `ab_pharmacy_delivery_assignment`
- **File**: `models/pharmacy_delivery_assignment.py`
- **Fields**:
  - `pilot_id` (Many2one to ab_pharmacy_delivery_pilot, required)
  - `branch_id` (Many2one to ab_pharmacy_delivery_branch, required)
  - `order_number` (char, required)
  - `transaction_type` (selection: delivery, order)
  - `status` (selection: assigned, done, cancelled)
  - `start_datetime`, `end_datetime` (datetime)
  - `assigned_by_user_id`, `completed_by_user_id` (Many2one res.users)
- **Constraint**: UNIQUE(branch_id, order_number, transaction_type)
- **Key Methods**:
  - `action_mark_done()`, `action_cancel()`

## Wizard
- **File**: `wizard/pharmacy_delivery_assignment_wizard.py`
- **Model**: `ab_pharmacy_delivery_assignment_wizard`

## Views (XML)
- `views/pharmacy_delivery_branch_views.xml`
- `views/pharmacy_delivery_pilot_views.xml`
- `views/pharmacy_delivery_assignment_views.xml`
- `views/pharmacy_delivery_dashboard_views.xml`
- `views/menus.xml`
- `wizard/pharmacy_delivery_assignment_wizard_views.xml`

## Security
- `security/groups.xml`
- `security/ir.model.access.csv`
- `security/record_rules.xml`

## Naming Conventions
- Model names: `ab_<name>` (e.g., `ab_pharmacy_delivery_pilot`)
- Table names follow: `ab_pharmacy_delivery_assignment`
- XML IDs: `ab_orders_management.<name>`

## Odoo 19.0 Key Differences
- Use `<list>` instead of `<tree>` for list views
- Use `models.Constraint` instead of `_sql_constraints`
- Use boolean expressions in XML instead of `attrs`
- Use ES modules for JavaScript (`@odoo-module`)
- Register assets in `__manifest__.py`

## Related Modules (dependencies)
- `ab_hr` - For HR employee/department integration
