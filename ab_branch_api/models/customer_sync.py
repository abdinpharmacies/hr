from odoo import models, fields
from odoo.exceptions import UserError

from .routing import current_request, request_store


class BranchCustomerSync(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _customer_reference_serial(self, ref):
        if not isinstance(ref, dict) or set(ref) != {'eplus_serial'}:
            return False
        serial = ref['eplus_serial']
        if type(serial) is not int or serial <= 0:
            raise UserError(self.env._('A valid customer E-Plus reference is required.'))
        return serial

    def _lock_customer_reference(self, serial):
        request_store(self).check_access('read')
        self._business_permissions('sale')
        self.env['ab_customer'].check_access('read')
        self.env['ab_sales_pos_api']._backend_lock_customer(serial)

    def _customer_from_branch_values(self, values):
        return self.env['ab_sales_pos_api']._backend_import_customer(values)

    def _resolve(self, model, ref):
        if model != 'ab_customer' or not current_request(self):
            return super()._resolve(model, ref)
        serial = self._customer_reference_serial(ref)
        if not serial:
            return super()._resolve(model, ref)
        Customer = self.env['ab_customer'].with_context(active_test=False)
        Customer.check_access('read')
        # Callcenter owns the selected identity; archived branch copies remain
        # valid references. Resolve duplicates deterministically without editing
        # customer masters, then enforce access in the original caller's env.
        matches = Customer.sudo().search(
            fields.Domain('eplus_serial', '=', serial), order='id asc', limit=1)
        if matches:
            customer = Customer.browse(matches.ids)
            customer.check_access('read')
            return customer
        store = request_store(self)
        pos = self.env['ab_sales_pos_api']
        values = pos._backend_customer_values(store, reference=serial)
        if not values:
            raise UserError(self.env._('The customer does not exist in this branch. Search by phone in the customer dialog and create the customer if not found.'))
        return self._customer_from_branch_values(values)
