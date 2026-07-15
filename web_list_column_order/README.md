# Web List Column Order

Adds per-user drag-to-reorder column ordering for Odoo 19 list views.

## Install

1. Ensure `/opt/odoo19/custom-addons` is in the Odoo addons path.
2. Update the apps list.
3. Install **Web List Column Order**.
4. Open any list view and drag a field column header left or right.

The saved order is scoped to the current user, model, and view id.

## Reset

Use the list view cog menu and click **Reset column order**. This removes the saved preference for the current user/model/view and restores the XML-defined order.

## Known Limitations

- Only normal field columns are draggable. Selection checkboxes, action columns, open-form columns, and the optional-column toggle stay in their native positions.
- Dynamically added virtual columns are appended after saved columns unless their field name already exists in the saved preference.
- Preferences are saved after drop. If the RPC fails, the current in-memory order remains until reload and the error is logged in the browser console.
- Inline editable rows are not draggable while a record is actively being edited.
