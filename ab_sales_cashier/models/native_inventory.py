from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeCashier(models.TransientModel):
    _inherit = 'ab_sales_cashier_api'

    @api.model
    def save_pending_invoice(self, invoice_id, request_id=None, store_id=None, wallet_id=None, document_type='sale', session_token=False):
        return super(NativeCashier, self.with_context(native_cashier_session_token=session_token)).save_pending_invoice(
            invoice_id, request_id=request_id, store_id=store_id, wallet_id=wallet_id,
            document_type=document_type, session_token=session_token)

    @api.model
    def _resolve_cashier_context(self, session_token=False, store_id=None, require_connection=False):
        session, profile, store = super()._resolve_cashier_context(session_token=session_token,
            store_id=store_id, require_connection=require_connection)
        if store and self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen', token=session_token)
        return session, profile, store

    @api.model
    def _coerce_store(self, store_id=None, required=False, require_connection=False, profile=False):
        store = super()._coerce_store(store_id=store_id, required=required,
                                     require_connection=False, profile=profile)
        if store and self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            return store
        return super()._coerce_store(store_id=store_id, required=required,
                                    require_connection=require_connection, profile=profile)

    @api.model
    def _fetch_pending_sale_headers_from_odoo(self, store, limit):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            return self.env['ab_sales_header'].search([('store_id', '=', store.id),
                ('native_submitted', '=', True), ('status', '=', 'pending')], order='id desc', limit=int(limit))
        return super()._fetch_pending_sale_headers_from_odoo(store, limit)

    @api.model
    def _pending_sales_source_odoo(self, store, limit):
        if self.env['ab_sales_backend']._is_native(store.id):
            headers = self._fetch_pending_sale_headers_from_odoo(store, limit)
            return [self._pending_sale_header_payload_from_odoo(header) for header in headers]
        return super()._pending_sales_source_odoo(store, limit)

    @api.model
    def _pending_sale_header_payload_from_odoo(self, header):
        result = super()._pending_sale_header_payload_from_odoo(header)
        if header.native_backend:
            result.update(id=header.id, invoice_number='N-%s' % header.id,
                          total_amount=header.native_totals['total_bill_net'],
                          total_net_amount=header.native_totals['total_bill_net'],
                          total_price=header.native_totals['total_bill'])
        return result

    @api.model
    def _sale_snapshot_source_odoo(self, store, invoice_id):
        result = super()._sale_snapshot_source_odoo(store, invoice_id)
        if result and self.env['ab_sales_backend']._is_native(store.id):
            header = self._get_cashier_sale_header_from_odoo(store, invoice_id)
            result['total_amount'] = header.native_totals['total_bill_net']
        return result

    @api.model
    def _pending_sales_source_bconnect(self, store, limit, excluded_invoice_ids=None):
        if self.env['ab_sales_backend']._is_native(store.id):
            return []
        return super()._pending_sales_source_bconnect(store, limit, excluded_invoice_ids)

    @api.model
    def _sale_snapshot_source_bconnect(self, store, invoice_id):
        if self.env['ab_sales_backend']._is_native(store.id):
            return {}
        return super()._sale_snapshot_source_bconnect(store, invoice_id)

    @api.model
    def _get_cashier_sale_header_from_odoo(self, store, invoice_id, pending_only=False):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            domain = [('id', '=', int(invoice_id)), ('store_id', '=', store.id), ('native_submitted', '=', True)]
            if pending_only:
                domain.append(('status', '=', 'pending'))
            return self.env['ab_sales_header'].search(domain, limit=1)
        return super()._get_cashier_sale_header_from_odoo(store, invoice_id, pending_only)

    @api.model
    def _get_cashier_sale_header_for_print(self, store, invoice_id):
        if store and self.env['ab_sales_backend']._is_native(store.id):
            return self._get_cashier_sale_header_from_odoo(store, invoice_id)
        return super()._get_cashier_sale_header_for_print(store, invoice_id)

    @api.model
    def _source_sale_header_for_return(self, return_header):
        if return_header.native_origin_id:
            return return_header.native_origin_id
        return super()._source_sale_header_for_return(return_header)

    @api.model
    def _get_cashier_return_header(self, store, return_id, pending_only=False):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            domain = [('id', '=', int(return_id)), ('store_id', '=', store.id), ('native_origin_id', '!=', False)]
            if pending_only:
                domain.append(('status', '=', 'pending'))
            return self.env['ab_sales_return_header'].search(domain, limit=1)
        return super()._get_cashier_return_header(store, return_id, pending_only)

    @api.model
    def _pending_return_header_payload_from_odoo(self, return_header):
        result = super()._pending_return_header_payload_from_odoo(return_header)
        if return_header.native_origin_id:
            result['total_amount'] = return_header.native_refund if return_header.native_posted else return_header._native_refund_amount()
            result['invoice_number'] = 'N-%s' % return_header.native_origin_id.id
        return result

    @api.model
    def _fetch_store_wallets_from_bconnect(self, store):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            balance = self.env['ab_sales_native_cash_balance'].search([
                ('store_id', '=', store.id), ('cashier_id', '=', self.env.uid)], limit=1)
            return [{'id': store.id, 'name': _('Native Cash'), 'balance': balance.amount if balance else 0.0}]
        return super()._fetch_store_wallets_from_bconnect(store)

    @api.model
    def _save_pending_invoice_in_bconnect(self, store, invoice_id, wallet_id, session=False):
        if not self.env['ab_sales_backend']._is_native(store.id):
            return super()._save_pending_invoice_in_bconnect(store, invoice_id, wallet_id, session=session)
        self.env['ab_sales_backend']._check_store(store.id, cashier=True)
        if int(wallet_id or 0) != store.id:
            raise ValidationError(_('Select this store\'s native cash wallet.'))
        header = self._get_cashier_sale_header_from_odoo(store, invoice_id)
        if not header:
            return 'not_found', '', 0.0
        with self.env.cr.savepoint():
            payment_id, created = self.env['ab_sales_native_payment']._settle(header)
        return ('saved' if created else 'already_saved'), 'saved', header.native_totals['total_bill_net']

    @api.model
    def _save_pending_return_in_odoo(self, store, return_id):
        if not self.env['ab_sales_backend']._is_native(store.id):
            return super()._save_pending_return_in_odoo(store, return_id)
        self.env['ab_sales_backend']._check_store(store.id, cashier=True)
        header = self._get_cashier_return_header(store, return_id)
        if not header:
            return 'not_found', '', 0.0
        with self.env.cr.savepoint():
            payment_id, created = self.env['ab_sales_native_payment']._settle(header.native_origin_id, header)
        return ('saved' if created else 'already_saved'), 'saved', header.native_refund

    @api.model
    def _sync_odoo_header_status(self, store, invoice_id):
        if self.env['ab_sales_backend']._is_native(store.id):
            return
        return super()._sync_odoo_header_status(store, invoice_id)


class NativeCashClose(models.Model):
    _name = 'ab_sales_native_cash_close'
    _description = 'Native Cashier Count'
    _order = 'id desc'

    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    cashier_id = fields.Many2one('res.users', required=True, readonly=True)
    expected_amount = fields.Float(readonly=True, digits=(18, 4))
    counted_amount = fields.Float(readonly=True, digits=(18, 4))
    difference = fields.Float(readonly=True, digits=(18, 4))

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Cash counts are recorded through the cashier closing screen.'))

    def write(self, vals):
        raise AccessError(_('Recorded cash counts cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Recorded cash counts cannot be deleted.'))


class NativeCashCloseWizard(models.TransientModel):
    _inherit = 'ab_sales_cashier_close_wizard'

    native_cashier_pin = fields.Char(string='Employee PIN', copy=False)
    native_backend = fields.Boolean(compute='_compute_native_backend')

    @api.depends('store_id')
    def _compute_native_backend(self):
        for rec in self:
            rec.native_backend = self.env['ab_sales_backend']._is_native(rec.store_id.id)

    def action_confirm_close(self):
        self.ensure_one()
        if not self.env['ab_sales_backend']._is_native(self.store_id.id):
            return super().action_confirm_close()
        store = self.env['ab_sales_backend']._check_store(self.store_id.id, cashier=True)
        token = self.env.context.get('native_cashier_session_token')
        if not token and 'ab_employee_access_sales_pos_session' in self.env.registry:
            session = self.env['ab_employee_access_sales_pos_session'].sudo().search([
                ('service_user_id', '=', self.env.uid), ('store_id', '=', store.id),
                ('employee_id', '=', self.employee_id.id), ('state', '=', 'active')], limit=1)
            if not session or not self.native_cashier_pin or not session._get_pos_profile().check_pos_pin(self.native_cashier_pin):
                raise AccessError(_('Enter the active cashier employee PIN to record the cash count.'))
            token = session.session_token
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen', token=token)
        if self.user_id != self.env.user or len(self.line_ids) != 1 or self.line_ids.wallet_id != store.id:
            raise AccessError(_('Cashier counts must use the current user and store wallet.'))
        store._lock_stock_scope()
        balance = self.env['ab_sales_native_cash_balance'].search([
            ('store_id', '=', store.id), ('cashier_id', '=', self.env.uid)], limit=1)
        amount = self.line_ids.net_balance
        import math
        if not math.isfinite(amount):
            raise ValidationError(_('Enter a finite counted cash amount.'))
        expected = balance.amount if balance else 0.0
        super(NativeCashClose, self.env['ab_sales_native_cash_close'].sudo()).create({
            'store_id': store.id, 'cashier_id': self.env.uid, 'expected_amount': expected,
            'counted_amount': amount, 'difference': amount - expected,
        })
        return {'type': 'ir.actions.act_window_close'}
