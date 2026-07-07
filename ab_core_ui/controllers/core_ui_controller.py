from odoo import http
from odoo.http import request


PREVIEW_DATA = {
    'core_ui.dialog.confirm': {
        'visible': True,
        'title': 'Confirm Approval',
        'message': 'Are you sure you want to approve Shipment #PO-2024-0042 from PharmaMed Supplies? This will release the inventory for distribution.',
        'cancel_label': 'Cancel',
        'confirm_label': 'Approve',
        'confirm_class': 'core_ui_btn_primary',
    },
    'core_ui.dialog.alert': {
        'visible': True,
        'title': 'Shipment Delayed',
        'message': 'Shipment #PO-2024-0042 from PharmaMed Supplies has been delayed by 48 hours due to customs inspection.',
        'icon': 'fa-info-circle',
        'icon_color': 'text-warning',
    },
    'core_ui.dialog.reject': {
        'visible': True,
        'title': 'Reject Transfer Request',
        'message': 'This will reject the stock transfer from Warehouse A to Warehouse B.',
        'cancel_label': 'Cancel',
        'confirm_label': 'Reject',
        'placeholder': 'Enter rejection reason...',
    },
    'core_ui.dialog.form': {
        'visible': True,
        'title': 'Add New Supplier',
        'icon': 'fa-edit',
        'cancel_label': 'Cancel',
        'save_label': 'Save Supplier',
    },
    'core_ui.card': {'title': 'Supplier Overview'},
    'core_ui.card.statistics': {
        'icon': 'fa-shopping-cart',
        'color': 'primary',
        'value': '1,284',
        'label': 'Active Purchase Orders',
        'trend': '+12.5%',
        'trend_direction': 'up',
    },
    'core_ui.card.hero': {
        'title': 'PharmaMed Supplies',
        'subtitle': 'Premium Pharmaceutical Distributor \u2022 15 years of partnership',
    },
    'core_ui.button.primary': {'label': 'Save Changes', 'icon': 'fa-save'},
    'core_ui.button.secondary': {'label': 'Cancel', 'icon': ''},
    'core_ui.button.ghost': {'label': 'More Details', 'icon': ''},
    'core_ui.button.danger': {'label': 'Delete Record', 'icon': 'fa-trash'},
    'core_ui.button.icon': {'icon': 'fa-cog', 'tooltip': 'Settings', 'size': ''},
    'core_ui.badge': {'label': 'In Stock', 'color': 'success', 'icon': 'fa-check-circle'},
    'core_ui.badge.state': {'label': 'Approved', 'state': 'approved'},
    'core_ui.alert.success': {
        'title': 'Inventory Updated',
        'message': 'Stock levels for Paracetamol 500mg have been updated successfully across all branches.',
    },
    'core_ui.alert.warning': {
        'title': 'Low Stock Alert',
        'message': 'Amoxicillin 250mg is below minimum threshold. Please reorder from supplier.',
    },
    'core_ui.alert.danger': {
        'title': 'Transfer Failed',
        'message': 'The stock transfer could not be completed. Insufficient quantity in source warehouse.',
    },
    'core_ui.alert.info': {
        'title': 'New Shipment Received',
        'message': 'Shipment #PO-2024-0042 has arrived at Warehouse A. 24 items pending inspection.',
    },
    'core_ui.toast.success': {
        'title': 'Operation Complete',
        'message': 'Stock adjustment has been applied successfully.',
    },
    'core_ui.toast.error': {
        'title': 'Error',
        'message': 'Failed to sync inventory data. Please try again.',
    },
    'core_ui.toast.warning': {
        'title': 'Warning',
        'message': 'This product is approaching its expiry date.',
    },
    'core_ui.table.modern': {
        'columns': [
            {'label': 'Product', 'name': 'product'},
            {'label': 'SKU', 'name': 'sku'},
            {'label': 'Qty', 'name': 'qty'},
            {'label': 'Price', 'name': 'price'},
            {'label': 'Status', 'name': 'status'},
        ],
        'rows': [
            {'product': 'Paracetamol 500mg', 'sku': 'PAR-001', 'qty': '2,400', 'price': '\u20aa0.35', 'status': 'In Stock'},
            {'product': 'Amoxicillin 250mg', 'sku': 'AMX-002', 'qty': '850', 'price': '\u20aa1.20', 'status': 'Low Stock'},
            {'product': 'Ibuprofen 400mg', 'sku': 'IBU-003', 'qty': '3,200', 'price': '\u20aa0.55', 'status': 'In Stock'},
            {'product': 'Omeprazole 20mg', 'sku': 'OME-004', 'qty': '0', 'price': '\u20aa0.90', 'status': 'Out of Stock'},
        ],
    },
    'core_ui.table.compact': {
        'columns': [
            {'label': 'Product', 'name': 'product'},
            {'label': 'SKU', 'name': 'sku'},
            {'label': 'Price', 'name': 'price'},
            {'label': 'Status', 'name': 'status'},
        ],
        'rows': [
            {'product': 'Paracetamol 500mg', 'sku': 'PAR-001', 'price': '\u20aa0.35', 'status': 'In Stock'},
            {'product': 'Amoxicillin 250mg', 'sku': 'AMX-002', 'price': '\u20aa1.20', 'status': 'Low Stock'},
            {'product': 'Ibuprofen 400mg', 'sku': 'IBU-003', 'price': '\u20aa0.55', 'status': 'In Stock'},
        ],
    },
    'core_ui.table.card': {
        'columns': [
            {'label': 'Product', 'name': 'product'},
            {'label': 'Supplier', 'name': 'supplier'},
            {'label': 'Qty', 'name': 'qty'},
            {'label': 'Status', 'name': 'status'},
        ],
        'rows': [
            {'product': 'Paracetamol 500mg', 'supplier': 'PharmaMed', 'qty': '2,400', 'status': 'Active'},
            {'product': 'Amoxicillin 250mg', 'supplier': 'MediCorp', 'qty': '850', 'status': 'Pending'},
            {'product': 'Ibuprofen 400mg', 'supplier': 'HealthPlus', 'qty': '3,200', 'status': 'Active'},
        ],
    },
    'core_ui.statistics.grid': {
        'stats': [
            {'icon': 'fa-shopping-cart', 'color': 'primary', 'value': '1,284', 'label': 'Active Orders', 'trend': '+12.5%', 'trend_direction': 'up'},
            {'icon': 'fa-boxes', 'color': 'success', 'value': '24,580', 'label': 'Items in Stock', 'trend': '+3.2%', 'trend_direction': 'up'},
            {'icon': 'fa-truck', 'color': 'warning', 'value': '18', 'label': 'Pending Deliveries', 'trend': '-2', 'trend_direction': 'down'},
            {'icon': 'fa-exclamation-triangle', 'color': 'danger', 'value': '6', 'label': 'Low Stock Alerts', 'trend': '+2', 'trend_direction': 'up'},
        ],
    },
    'core_ui.empty.no_data': {
        'title': 'No Suppliers Found',
        'message': 'There are no suppliers added yet. Click the button below to add your first supplier.',
        'action_label': 'Add Supplier',
        'action_icon': 'fa-plus',
    },
    'core_ui.empty.no_results': {
        'title': 'No Results Found',
        'message': 'No products match your search criteria. Try different keywords or adjust your filters.',
    },
    'core_ui.empty.permission': {
        'title': 'Access Restricted',
        'message': 'You do not have permission to access the inventory module. Contact your administrator.',
        'contact_admin': True,
    },
    'core_ui.loading.spinner': {'size': 'lg'},
    'core_ui.loading.skeleton': {},
    'core_ui.header.page': {
        'title': 'Purchase Orders',
        'subtitle': 'Manage supplier orders and track deliveries',
    },
    'core_ui.progress.bar': {
        'label': 'Inventory Audit Progress',
        'value': 68,
        'show_value': True,
        'color': '',
    },
    'core_ui.progress.circle': {
        'value': 78,
        'size': 80,
        'stroke': 6,
        'circumference': 213.62830044410595,
        'offset': 46.99882609770331,
    },
    'core_ui.nav.breadcrumb': {
        'items': [
            {'label': 'Dashboard', 'url': '#'},
            {'label': 'Inventory', 'url': '#'},
            {'label': 'Products', 'url': '#'},
            {'label': 'Paracetamol 500mg'},
        ],
    },
    'core_ui.nav.tabs': {
        'tabs': [
            {'label': 'Overview', 'icon': 'fa-info-circle', 'active': True},
            {'label': 'Stock', 'icon': 'fa-boxes'},
            {'label': 'Orders', 'icon': 'fa-shopping-cart'},
            {'label': 'Analytics', 'icon': 'fa-chart-bar'},
        ],
    },
    'core_ui.status.dot': {'color': 'green', 'label': 'Online'},
    'core_ui.input.text': {
        'label': 'Product Name',
        'placeholder': 'Enter product name...',
        'value': 'Paracetamol 500mg',
        'help_text': 'Use the official scientific name.',
    },
    'core_ui.input.select': {
        'label': 'Supplier',
        'placeholder': 'Select a supplier...',
        'options': [
            {'label': 'PharmaMed Supplies', 'value': '1'},
            {'label': 'MediCorp International', 'value': '2'},
            {'label': 'HealthPlus Distributors', 'value': '3'},
        ],
        'value': '1',
    },
    'core_ui.input.toggle': {
        'label': 'Enable Auto-Reorder',
        'active': True,
    },
    'core_ui.avatar': {
        'name': 'Alhassan Hossny',
        'initials': 'AH',
        'size': 'lg',
        'show_status': True,
        'status': 'online',
    },
    'core_ui.timeline': {
        'stages': [
            {'label': 'Secretarial', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed', 'notes': 'تم إنشاء الطلب'},
            {'label': 'Rejection', 'icon': '✗', 'dot_class': 'is-event-rejection', 'line_class': 'pending', 'is_event': True, 'event_type': 'rejection', 'user': 'AB Request Test User 3', 'notes': 'Reason: werwer'},
            {'label': 'Inventory', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed'},
            {'label': 'Rejection', 'icon': '✗', 'dot_class': 'is-event-rejection', 'line_class': 'pending', 'is_event': True, 'event_type': 'rejection', 'user': '53-فرع المعادي 2 القاهرة', 'notes': 'Reason: dsf'},
            {'label': 'Purchase', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed'},
            {'label': 'Suppliers', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed'},
            {'label': 'Bank Account', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed'},
            {'label': 'Sign Check', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed'},
            {'label': 'Supplier Notification', 'icon': '✓', 'dot_class': 'is-completed', 'line_class': 'completed', 'label_class': 'completed', 'notes': 'werwer'},
            {'label': 'Check delivery', 'icon': '✈', 'dot_class': 'is-overdue', 'line_class': 'pending', 'label_class': 'overdue'},
        ],
        'current_stage': {
            'label': 'Check delivery',
            'is_overdue': True,
            'user': 'AB Request Test User 2',
            'date': '2026-07-01T11:40:47',
        },
    },
    'core_ui.search': {
        'placeholder': 'Search products, suppliers, orders...',
        'value': '',
        'width': '320px',
    },
    'core_ui.upload.zone': {
        'title': 'Upload Inventory File',
        'description': 'Drag and drop your CSV or Excel file here, or click to browse.',
    },
    'core_ui.wizard.stepper': {
        'steps': [
            {'label': 'Select Products', 'state': 'completed'},
            {'label': 'Review Quantities', 'state': 'active'},
            {'label': 'Confirm Transfer', 'state': ''},
            {'label': 'Done', 'state': ''},
        ],
    },
    'core_ui.kanban.card': {
        'title': 'PharmaMed Supplies',
        'subtitle': 'Q4 Contract - $124,500',
        'badges': [
            {'label': 'Active', 'color': 'success'},
            {'label': 'Priority', 'color': 'warning'},
        ],
    },
    'core_ui.form.modern': {},
}


def _get_view_id_by_name(name):
    """Find a QWeb template by its 'name' field and return its DB id."""
    views = request.env['ir.ui.view'].sudo().search([
        ('name', '=', name),
        ('type', '=', 'qweb'),
    ], limit=1)
    return views.id if views else 0


class CoreUIQWebController(http.Controller):

    @http.route('/core_ui/render_previews', type='json', auth='user', methods=['POST'])
    def render_previews(self, components):
        qweb = request.env['ir.qweb']
        previews = {}
        errors = {}

        for comp in components:
            cid = comp.get('component_id', '')
            template_ref = comp.get('template_ref', '')
            comp_id = comp.get('id')
            all_errors = []

            # Strategy 1) Component template + preview data by name -> integer ID
            # Preferred path: render the real template directly with mock data.
            # No t-call resolution needed, no ir.model.data dependency.
            if template_ref:
                view_id = _get_view_id_by_name(template_ref)
                if view_id:
                    ctx = PREVIEW_DATA.get(cid, {})
                    try:
                        html = qweb._render(view_id, ctx)
                        previews[str(comp_id)] = html
                        continue
                    except Exception as e:
                        all_errors.append(f'template+data failed: {e}')
                    try:
                        html = qweb._render(view_id, {})
                        previews[str(comp_id)] = html
                        continue
                    except Exception as e:
                        all_errors.append(f'template+empty failed: {e}')
                else:
                    all_errors.append(f'component template not found: {template_ref}')
            else:
                all_errors.append('no template_ref defined')

            # Strategy 2) Preview template by name -> integer ID (fallback)
            pid = 'core_ui.preview.' + cid.replace('core_ui.', '', 1)
            view_id = _get_view_id_by_name(pid)
            if view_id:
                try:
                    html = qweb._render(view_id, {})
                    previews[str(comp_id)] = html
                    continue
                except Exception as e:
                    all_errors.append(f'preview failed: {e}')
            else:
                all_errors.append(f'preview template not found: {pid}')

            if all_errors:
                errors[cid] = all_errors

        return {'previews': previews, 'errors': errors}
