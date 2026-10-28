from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeSalesInventoryProcess(models.AbstractModel):
    _inherit = 'ab_inventory_process'

    @api.model
    def _native_manager_scope(self):
        return (self.env.context.get('ab_sales_branch_scope')
                and self.env.user.has_group('ab_sales.group_ab_sales_manager'))

    @api.model
    def _check_store(self, store_id):
        if self._native_manager_scope():
            store = self.env['ab_store'].browse(int(store_id)).exists()
            if not store:
                raise ValidationError(_('Select a valid store.'))
            return store
        return super()._check_store(store_id)

    @api.model
    def get_balance(self, store_id, product_id=None, source_id=None, before=None):
        if self._native_manager_scope():
            elevated = self.with_user(SUPERUSER_ID)
            return super(NativeSalesInventoryProcess, elevated).get_balance(
                store_id, product_id=product_id, source_id=source_id, before=before)
        return super().get_balance(store_id, product_id=product_id, source_id=source_id, before=before)

    @api.model
    def _source_balances(self, store_id, product_id=None, before=None,
                         source_ids=None, include_zero=True, include_pending_outgoing=False):
        if self._native_manager_scope():
            elevated = self.with_user(SUPERUSER_ID)
            return super(NativeSalesInventoryProcess, elevated)._source_balances(
                store_id, product_id=product_id, before=before, source_ids=source_ids,
                include_zero=include_zero, include_pending_outgoing=include_pending_outgoing)
        return super()._source_balances(
            store_id, product_id=product_id, before=before, source_ids=source_ids,
            include_zero=include_zero, include_pending_outgoing=include_pending_outgoing)


class NativeSalesBackend(models.Model):
    _name = 'ab_sales_backend'
    _description = 'Sales Inventory Backend'
    _rec_name = 'store_id'

    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    backend = fields.Selection([('legacy', 'E-Plus'), ('native', 'Native Inventory')],
                               required=True, default='legacy')
    _store_unique = models.Constraint('UNIQUE(store_id)', 'Each store has one sales backend.')

    @api.model
    def _is_native(self, store_id):
        return bool(self.sudo().search([('store_id', '=', int(store_id or 0)),
                                        ('backend', '=', 'native')], limit=1))

    @api.model
    def _check_store(self, store_id, cashier=False):
        user = self.env.user
        is_system = user.has_group('base.group_system')
        is_sales_manager = user.has_group('ab_sales.group_ab_sales_manager')
        sales = self.env['ab_sales_header']
        if hasattr(sales, '_raise_sales_prevented'):
            sales._raise_sales_prevented()
        if not (is_system
                or is_sales_manager
                or user.has_group('ab_sales_inventory.group_native_sales_user')):
            raise AccessError(_('Native sales access is required.'))
        if cashier and not (is_system
                            or is_sales_manager
                            or user.has_group('ab_sales.group_ab_sales_cashier')):
            raise AccessError(_('Cashier access is required.'))
        if is_system or is_sales_manager:
            store = self.env['ab_store'].browse(int(store_id)).exists()
        else:
            store = self.env['ab_inventory_process'].with_context(
                ab_sales_branch_scope=True)._check_store(int(store_id))
        if not store or not store.allow_sale:
            raise AccessError(_('This store is unavailable for native sales.'))
        return store

    @api.model
    def _check_employee_session(self, store, permission, token=False):
        if 'ab_employee_access_sales_pos_api' not in self.env.registry:
            return False
        token = token or self.env.context.get('native_pos_hr_token') or self.env.context.get('ab_return_session_token') or self.env.context.get('native_cashier_session_token')
        session = self.env['ab_employee_access_sales_pos_api']._get_session(token, states=['active'])
        profile = session._get_pos_profile()
        if session.service_user_id != self.env.user or not profile or not profile._is_store_allowed_for_pos(store):
            raise AccessError(_('The employee session must belong to this service user and store.'))
        permissions = profile._effective_pos_permissions()
        if not permissions.get(permission) or (permission == 'allow_pos_screen' and permissions.get('allow_sale') is False):
            raise AccessError(_('The employee profile does not permit this native operation.'))
        if permission == 'allow_return':
            if permissions.get('require_manager_for_return') and not permissions.get('allow_manager_approval'):
                raise AccessError(_('This return requires an employee authorized to approve returns.'))
        return session

    def _check_configuration(self, store_ids, activating_native=False):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can change the sales backend.'))
        stores = self.env['ab_store'].browse(store_ids).exists()
        if len(stores) != len(set(store_ids)):
            raise AccessError(_('Select valid sales backend stores.'))
        stores._lock_stock_scope()
        for model in ('ab_sales_header', 'ab_sales_return_header'):
            domain = fields.Domain('store_id', 'in', stores.ids) & fields.Domain('status', 'in', ['prepending', 'pending'])
            if activating_native:
                domain &= fields.Domain('native_backend', '=', True) if model == 'ab_sales_header' else fields.Domain('native_origin_id', '!=', False)
            if self.env[model].sudo().search_count(domain):
                raise ValidationError(_('Complete open sales and returns before changing the backend.'))

    @api.model_create_multi
    def create(self, vals_list):
        for backend in {'native', 'legacy'}:
            store_ids = [v.get('store_id') for v in vals_list if v.get('backend', 'legacy') == backend]
            if store_ids:
                self._check_configuration(store_ids, activating_native=backend == 'native')
        return super().create(vals_list)

    def write(self, vals):
        if (vals.get('backend') == 'legacy' or 'store_id' in vals) and self.env['ab_sales_header'].sudo().search_count([
                ('store_id', 'in', self.mapped('store_id').ids), ('native_posted', '=', True)]):
            raise ValidationError(_('A store with posted native sales must keep its native backend for returns.'))
        self._check_configuration(self.mapped('store_id').ids + ([vals['store_id']] if vals.get('store_id') else []),
                                  activating_native=vals.get('backend') == 'native' and 'store_id' not in vals)
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_('Change the backend setting instead of deleting it.'))


class NativeSalesPayment(models.Model):
    _name = 'ab_sales_native_payment'
    _description = 'Native Sale Payment or Refund'
    _order = 'id desc'

    operation_key = fields.Char(required=True, index=True, readonly=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    cashier_id = fields.Many2one('res.users', required=True, readonly=True)
    employee_id = fields.Many2one('ab_hr_employee', readonly=True, ondelete='restrict', index=True)
    sale_id = fields.Many2one('ab_sales_header', required=True, readonly=True, ondelete='restrict')
    return_id = fields.Many2one('ab_sales_return_header', readonly=True, ondelete='restrict')
    kind = fields.Selection([('payment', 'Payment'), ('refund', 'Refund')], required=True, readonly=True)
    amount = fields.Float(required=True, readonly=True, digits=(18, 4))
    balance_after = fields.Float(readonly=True, digits=(18, 4))
    _operation_unique = models.Constraint('UNIQUE(operation_key)', 'Payment operation keys must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Payments are created only by cashier settlement.'))

    def write(self, vals):
        raise AccessError(_('Settled payments and refunds cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Settled payments and refunds cannot be deleted.'))

    @api.model
    def _settle(self, sale, return_header=False):
        with self.env.cr.savepoint():
            return self._settle_transaction(sale, return_header)

    def _settle_transaction(self, sale, return_header=False):
        self = self.with_context(ab_sales_branch_scope=True)
        store = self.env['ab_sales_backend']._check_store(sale.store_id.id, cashier=True)
        session = self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen')
        sale.check_access('read')
        sale.lock_for_update(allow_referencing=True)
        sale.invalidate_recordset()
        if return_header and (return_header.native_origin_id != sale or return_header.store_id != store):
            raise AccessError(_('The refund and original invoice must belong to the same store.'))
        document = return_header or sale
        document.check_access('read')
        key = 'refund:%s' % document.id if return_header else 'payment:%s' % sale.id
        existing = self.sudo().search([('operation_key', '=', key)], limit=1)
        if existing:
            return existing.id, False
        if document.status != 'pending' or not sale.native_submitted or not sale.native_backend:
            raise ValidationError(_('Only submitted pending native documents can be settled.'))
        if not return_header:
            sale._validate_native_approval()
        if return_header and not return_header.native_posted:
            raise ValidationError(_('The pending native return has no completed stock restoration.'))
        amount = float(return_header.native_refund if return_header else sale.native_totals['total_bill_net'])
        if return_header:
            amount = -amount
        store._lock_stock_scope()
        Balance = self.env['ab_sales_native_cash_balance'].sudo()
        balance = Balance.search([('store_id', '=', store.id), ('cashier_id', '=', self.env.uid)], limit=1)
        if not balance:
            balance = super(NativeSalesCashBalance, Balance).create({'store_id': store.id, 'cashier_id': self.env.uid})
        new_balance = balance.amount + amount
        super(NativeSalesCashBalance, balance).write({'amount': new_balance})
        payment = super(NativeSalesPayment, self.sudo()).create({
            'operation_key': key, 'store_id': store.id, 'cashier_id': self.env.uid,
            'employee_id': session.employee_id.id if session else False,
            'sale_id': sale.id, 'return_id': return_header.id if return_header else False,
            'kind': 'refund' if return_header else 'payment', 'amount': amount, 'balance_after': new_balance,
        })
        document._native_settled()
        return payment.id, True


class NativeSalesCashBalance(models.Model):
    _name = 'ab_sales_native_cash_balance'
    _description = 'Native Cashier Balance'

    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    cashier_id = fields.Many2one('res.users', required=True, readonly=True)
    amount = fields.Float(readonly=True, digits=(18, 4))
    _cashier_store_unique = models.Constraint('UNIQUE(store_id, cashier_id)', 'A cashier has one balance per store.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Cashier balances are maintained only by settlement.'))

    def write(self, vals):
        raise AccessError(_('Cashier balances are maintained only by settlement.'))

    def unlink(self):
        raise AccessError(_('Cashier balances cannot be deleted.'))
