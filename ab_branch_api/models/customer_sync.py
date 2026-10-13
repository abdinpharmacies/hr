import logging

from odoo import models, fields
from odoo.exceptions import UserError

from .routing import current_request, request_store, selected_server


_logger = logging.getLogger(__name__)


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
        self._lock_operation('customer-reference:%s' % serial)

    def _customer_from_branch_values(self, values):
        store = request_store(self)
        serial = self._customer_reference_serial({'eplus_serial': values.get('eplus_serial')})
        self._lock_customer_reference(serial)
        if not values.get('active') or not (values.get('name') or '').strip():
            raise UserError(self.env._('The branch customer is inactive or incomplete. Review the customer before using it.'))
        Customer = self.env['ab_customer'].with_context(active_test=False)
        matches = Customer.sudo().search(fields.Domain('eplus_serial', '=', serial), limit=2)
        if len(matches) > 1:
            raise UserError(self.env._('The customer reference is duplicated on this branch. Review the customer records before retrying.'))
        customer = Customer.browse(matches.ids)
        allowed = {'code', 'name', 'address', 'mobile_phone', 'work_phone', 'last_update_date',
                   'eplus_serial', 'eplus_create_date'}
        values = {key: value for key, value in values.items() if key in allowed}
        if customer:
            customer.check_access('read')
            if not customer.active:
                raise UserError(self.env._('The customer is archived on this branch. Review the customer before using it.'))
            customer.sudo().write(values)
        else:
            Customer.check_access('create')
            customer = Customer.create(dict(values, default_store_id=store.id, active=True))
            customer.check_access('read')
            _logger.info('Branch API imported customer E-Plus reference %s for store %s by user %s',
                         serial, store.id, self.env.uid)
        return customer

    def _resolve(self, model, ref):
        if model != 'ab_customer' or not current_request(self):
            return super()._resolve(model, ref)
        serial = self._customer_reference_serial(ref)
        if not serial:
            return super()._resolve(model, ref)
        Customer = self.env['ab_customer'].with_context(active_test=False)
        Customer.check_access('read')
        matches = Customer.sudo().search(fields.Domain('eplus_serial', '=', serial), limit=2)
        if matches:
            if len(matches) != 1 or not matches.active:
                raise UserError(self.env._('The selected customer is missing, inactive or duplicated on this branch. Synchronize customers or select another customer.'))
            customer = Customer.browse(matches.ids)
            customer.check_access('read')
            return customer
        store = request_store(self)
        pos = self.env['ab_sales_pos_api']
        with pos.connect_eplus(server=selected_server(self, store), param_str='?', charset='CP1256', autocommit=False) as connection:
            with connection.cursor() as cursor:
                row = pos._bconnect_customer_by_id(cursor, serial)
        if not row or int(row.get('eplus_serial') or 0) != serial:
            raise UserError(self.env._('The customer does not exist in this branch. Search by phone in the customer dialog and create the customer if not found.'))
        return self._customer_from_branch_values(pos._customer_vals_from_bconnect(row, store))


class BranchPosCustomerSync(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _upsert_customer_from_bconnect(self, vals):
        if not current_request(self):
            return super()._upsert_customer_from_bconnect(vals)
        return self.env['ab_branch_api']._customer_from_branch_values(vals)
