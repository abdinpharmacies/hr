from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .cash_shift import money


class ShiftSettlement(models.Model):
    _inherit = 'ab_sales_native_payment'

    def _settle_transaction(self, sale, return_header=False):
        store = self.env['ab_sales_backend']._check_store(sale.store_id.id, cashier=True)
        drawer = self.env['ab_sales_cash_drawer']._for_store(store)
        if not drawer:
            return super()._settle_transaction(sale, return_header)
        token = self.env.context.get('native_cashier_session_token')
        session = drawer._session(token)
        sale.check_access('read')
        sale.lock_for_update(allow_referencing=True)
        sale.invalidate_recordset()
        key = 'refund:%s' % return_header.id if return_header else 'payment:%s' % sale.id
        if self.sudo().search_count([('operation_key', '=', key)], limit=1):
            return super()._settle_transaction(sale, return_header)
        shift = drawer._require_open(token)
        amount = drawer.currency_id.round(return_header._native_refund_amount() if return_header else sale.native_totals['total_bill_net'])
        rows = self.env.context.get('cash_shift_tenders')
        if not isinstance(rows, list) or len(rows) > 20:
            raise ValidationError(_('Use the Shift Cashier screen and enter the payment breakdown.'))
        drawer.method_ids.lock_for_update(allow_referencing=True)
        drawer.method_ids.invalidate_recordset()
        prepared = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('method_id'), int):
                raise ValidationError(_('Choose a valid payment method.'))
            method = drawer.method_ids.filtered(lambda item: item.id == row['method_id'] and item.active)
            if not method or method.id in seen:
                raise ValidationError(_('Use each accepted payment method at most once.'))
            seen.add(method.id)
            value = money(row.get('amount'), drawer.currency_id)
            reference = str(row.get('reference') or '').strip()
            if value <= 0 or (method.require_reference and not reference):
                raise ValidationError(_('Positive payments require the configured transaction reference.'))
            if len(reference) > 120:
                raise ValidationError(_('Transaction references must not exceed 120 characters.'))
            prepared.append({'method_id': method.id, 'amount': value, 'reference': reference, 'cash': method.kind == 'cash'})
        if not drawer.currency_id.is_zero(sum(row['amount'] for row in prepared) - amount):
            raise ValidationError(_('The payment breakdown must equal the amount due.'))
        if return_header:
            original = self.env['ab_sales_cash_event'].search([('payment_id.sale_id', '=', sale.id), ('payment_id.kind', '=', 'payment')], limit=1)
            if not original:
                raise ValidationError(_('This sale predates cash shifts; its refund requires historical review.'))
            previous = self.env['ab_sales_cash_tender'].search([
                ('event_id.payment_id.sale_id', '=', sale.id), ('event_id.payment_id.kind', '=', 'refund')])
            for row in prepared:
                collected = sum(original.tender_ids.filtered(lambda item: item.method_id.id == row['method_id']).mapped('amount'))
                refunded = -sum(previous.filtered(lambda item: item.method_id.id == row['method_id']).mapped('amount'))
                if drawer.currency_id.compare_amounts(row['amount'], collected - refunded) > 0:
                    raise ValidationError(_('Refund each payment method only up to its remaining original amount.'))
        sign = -1 if return_header else 1
        cash = sign * sum(row['amount'] for row in prepared if row['cash'])
        if drawer.currency_id.compare_amounts(shift.cash_amount + cash, 0) < 0:
            raise ValidationError(_('The drawer does not have enough physical cash for this refund.'))
        payment_id, created = super()._settle_transaction(sale, return_header)
        if created:
            event = self.env['ab_sales_cash_event']._insert({
                'shift_id': shift.id, 'payment_id': payment_id, 'employee_id': session.employee_id.id,
                'session_id': session.id, 'total_amount': sign * amount, 'cash_amount': cash})
            for row in prepared:
                self.env['ab_sales_cash_tender']._insert({
                    'event_id': event.id, 'method_id': row['method_id'],
                    'amount': sign * row['amount'], 'reference': row['reference']})
            shift._update({'cash_amount': drawer.currency_id.round(shift.cash_amount + cash)})
        return payment_id, created


class ShiftSale(models.Model):
    _inherit = 'ab_sales_header'

    def action_push_to_eplus(self):
        for sale in self.filtered(lambda record: record.native_backend and not record.native_submitted):
            store = self.env['ab_sales_backend']._check_store(sale.store_id.id)
            drawer = self.env['ab_sales_cash_drawer']._for_store(store)
            if drawer:
                drawer._require_open(responsible=False)
        return super().action_push_to_eplus()


class ShiftCashier(models.TransientModel):
    _inherit = 'ab_sales_cashier_api'

    def _fetch_store_wallets_from_bconnect(self, store):
        drawer = self.env['ab_sales_cash_drawer']._for_store(store)
        if drawer:
            self.env['ab_sales_backend']._check_store(store.id, cashier=True)
            shift = drawer._current()
            return [{'id': store.id, 'name': _('Shared Branch Drawer'), 'balance': shift.cash_amount if shift else 0.0}]
        return super()._fetch_store_wallets_from_bconnect(store)

    @api.model
    def open_cash_shift_operation(self, session_token, store_id, invoice_id=False, document_type='sale'):
        session, profile, store = self._resolve_cashier_context(session_token=session_token, store_id=store_id)
        drawer = self.env['ab_sales_cash_drawer']._for_store(store)
        if not drawer:
            raise ValidationError(_('Configure and enable this branch cash drawer first.'))
        context = {'default_drawer_id': drawer.id, 'default_session_token': session_token}
        if invoice_id:
            drawer._require_open(session_token)
            model = 'ab_sales_return_header' if document_type == 'return' else 'ab_sales_header'
            document = self.env[model].browse(int(invoice_id)).exists()
            document.check_access('read')
            if not document or document.store_id != store:
                raise AccessError(_('The document must belong to this branch.'))
            context.update(default_operation='settle', **{
                'default_return_id' if document_type == 'return' else 'default_sale_id': document.id})
        else:
            shift = drawer._current()
            if not shift:
                raise ValidationError(_('A cash manager must prepare the first opening float.'))
            context.update(default_operation='accept' if shift.state == 'waiting' else 'close', default_shift_id=shift.id)
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new', 'context': context}


class ShiftOldClose(models.TransientModel):
    _inherit = 'ab_sales_cashier_close_wizard'

    def action_confirm_close(self):
        for wizard in self:
            if self.env['ab_sales_cash_drawer']._for_store(wizard.store_id):
                raise ValidationError(_('Use Shift Cashier to close the shared drawer and record the handover.'))
        return super().action_confirm_close()


class CashShiftStore(models.Model):
    _inherit = 'ab_store'

    cash_drawer_ids = fields.One2many('ab_sales_cash_drawer', 'store_id', string='Shared Cash Drawer Configuration')
