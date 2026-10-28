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
        shift = drawer._require_open(token, create=True)
        amount = drawer.currency_id.round(return_header._native_refund_amount() if return_header else sale.native_totals['total_bill_net'])
        rows = self.env.context.get('cash_shift_tenders')
        original = self.env['ab_sales_cash_event']
        previous = self.env['ab_sales_cash_tender']
        if return_header:
            original = self.env['ab_sales_cash_event'].search([
                ('payment_id.sale_id', '=', sale.id), ('payment_id.kind', '=', 'payment')], limit=1)
            if not original:
                raise ValidationError(_('This sale predates cash shifts; its refund requires historical review.'))
            previous = self.env['ab_sales_cash_tender'].search([
                ('event_id.payment_id.sale_id', '=', sale.id), ('event_id.payment_id.kind', '=', 'refund')])
        drawer.method_ids.lock_for_update(allow_referencing=True)
        drawer.method_ids.invalidate_recordset()
        if rows is None or rows == []:
            if return_header:
                rows = []
                remaining = amount
                for tender in original.tender_ids.sorted('id'):
                    refunded = -sum(previous.filtered(
                        lambda item: item.method_id == tender.method_id).mapped('amount'))
                    available = drawer.currency_id.round(tender.amount - refunded)
                    value = min(remaining, available)
                    if drawer.currency_id.compare_amounts(value, 0) > 0:
                        rows.append({'method_id': tender.method_id.id, 'amount': value,
                                     'reference': tender.reference})
                        remaining = drawer.currency_id.round(remaining - value)
                    if drawer.currency_id.is_zero(remaining):
                        break
                if not drawer.currency_id.is_zero(remaining):
                    raise ValidationError(_('Refund each payment method only up to its remaining original amount.'))
            else:
                cash_method = drawer.method_ids.filtered(lambda item: item.active and item.kind == 'cash').sorted('id')[:1]
                if not cash_method:
                    raise ValidationError(_('Choose a valid payment method.'))
                rows = [{'method_id': cash_method.id, 'amount': amount, 'reference': ''}]
        elif not isinstance(rows, list) or len(rows) > 20:
            raise ValidationError(_('Use the Shift Cashier screen and enter the payment breakdown.'))
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
        difference = drawer.currency_id.round(amount - sum(row['amount'] for row in prepared))
        if drawer.currency_id.compare_amounts(difference, 0) > 0:
            cash_row = next((row for row in prepared if row['cash']), False)
            if cash_row:
                cash_row['amount'] = drawer.currency_id.round(cash_row['amount'] + difference)
            else:
                cash_method = drawer.method_ids.filtered(
                    lambda item: item.active and item.kind == 'cash' and item.id not in seen).sorted('id')[:1]
                if not cash_method:
                    raise ValidationError(_('Choose a valid payment method.'))
                prepared.append({'method_id': cash_method.id, 'amount': difference,
                                 'reference': '', 'cash': True})
        elif drawer.currency_id.compare_amounts(difference, 0) < 0:
            raise ValidationError(_('Payment amounts cannot exceed the amount due.'))
        if return_header:
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
            return False
        if invoice_id:
            return False
        context = {'default_drawer_id': drawer.id, 'default_session_token': session_token}
        shift = drawer._current()
        if not shift:
            raise ValidationError(_('The first collection will open a zero-balance wallet. There is no active wallet to hand over yet.'))
        if session.employee_id != shift.employee_id:
            raise AccessError(_('This branch wallet belongs to another cashier. Complete the formal handover first.'))
        context.update(default_operation='accept' if not shift.accepted_at else 'close', default_shift_id=shift.id)
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_cash_operation',
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new', 'context': context}


class ShiftOldClose(models.TransientModel):
    _inherit = 'ab_sales_cashier_close_wizard'

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        store = self.env['ab_store'].browse(result.get('store_id')).exists()
        drawer = self.env['ab_sales_cash_drawer']._for_store(store) if store else False
        token = self.env.context.get('native_cashier_session_token')
        if drawer and token:
            result['employee_id'] = drawer._session(token).employee_id.id
        return result

    def action_confirm_close(self):
        self.ensure_one()
        drawer = self.env['ab_sales_cash_drawer']._for_store(self.store_id)
        if not drawer:
            return super().action_confirm_close()
        self.check_access('write')
        drawer.check_access('read')
        if drawer.company_id not in self.env.companies:
            raise AccessError(_('The drawer must belong to an allowed company.'))
        drawer._lock()
        if not drawer.enabled or not drawer.active:
            raise ValidationError(_('Enable the drawer before performing cash operations.'))
        session = drawer._session(self.env.context.get('native_cashier_session_token'))
        shift = drawer._current()
        if not shift or shift.state != 'open':
            raise ValidationError(_('This is not the active cashier wallet. Refresh the screen.'))
        if session.employee_id != shift.employee_id or self.employee_id != shift.employee_id:
            raise AccessError(_('Only the responsible cashier can close this drawer shift.'))
        if self.user_id != self.env.user or len(self.line_ids) != 1 or self.line_ids.wallet_id != self.store_id.id:
            raise AccessError(_('This is not the active cashier wallet. Refresh the screen.'))
        amount = money(self.line_ids.net_balance, drawer.currency_id)
        variance = drawer.currency_id.round(amount - shift.cash_amount)
        shift._update({
            'state': 'closed',
            'closed_at': fields.Datetime.now(),
            'closed_user_id': self.env.uid,
            'counted_amount': amount,
            'carry_amount': 0,
            'variance': variance,
            'review_state': 'pending' if variance else 'none',
        })
        return {'type': 'ir.actions.act_window_close'}


class CashShiftStore(models.Model):
    _inherit = 'ab_store'

    cash_drawer_ids = fields.One2many('ab_sales_cash_drawer', 'store_id', string='Shared Cash Drawer Configuration')
