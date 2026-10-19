from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class CashShiftAccounting(models.Model):
    _inherit = 'ab_sales_cash_shift'

    def _accounting_configuration(self):
        self.ensure_one()
        self.check_access('read')
        if self.company_id not in self.env.companies:
            raise ValidationError(_('The cash shift must belong to an allowed company.'))
        return self.env['ab_accounting_cash_config']._for_store(self.store_id, self.company_id).with_context(tz='Africa/Cairo')

    def _post_closing_accounts(self):
        self.ensure_one()
        config = self._accounting_configuration()
        if not config:
            return
        if self.state != 'closed':
            raise ValidationError(_('Close the shift before posting its accounting batch.'))
        amounts = defaultdict(float)
        roles = {'cash': 'drawer_account_id', 'card': 'card_account_id',
                 'wallet': 'wallet_account_id', 'other': 'other_account_id'}
        for event in self.event_ids:
            payment = event.payment_id
            sale = payment.sale_id
            if sale.store_id != self.store_id or sale.company_id != self.company_id:
                raise ValidationError(_('All closing transactions must belong to the shift branch and company.'))
            if (sale.native_totals or {}).get('total_tax'):
                raise ValidationError(_('Nonzero sales tax requires an approved allocation before automatic cash accounting.'))
            if event.total_amount != sum(event.tender_ids.mapped('amount')) and not self.currency_id.is_zero(event.total_amount - sum(event.tender_ids.mapped('amount'))):
                raise ValidationError(_('The recorded payment breakdown does not match the settlement.'))
            for tender in event.tender_ids:
                amounts[roles[tender.method_id.kind]] += tender.amount
            refund = payment.kind == 'refund'
            amounts['sales_return_account_id' if refund else 'sales_account_id'] -= event.total_amount
            domain = fields.Domain('store_id', '=', self.store_id.id)
            if refund:
                domain &= fields.Domain('return_line_id.header_id', '=', payment.return_id.id)
            else:
                domain &= fields.Domain('sale_line_id.header_id', '=', sale.id) & fields.Domain('return_line_id', '=', False)
            allocations = self.env['ab_sales_stock_allocation'].sudo().search(domain)
            if any(item.source_id.unit_taxes_value for item in allocations):
                raise ValidationError(_('Taxed stock requires an approved valuation allocation before automatic cash accounting.'))
            sources = allocations.source_id
            purchases = self.env['ab_purchase_header'].sudo().browse(sources.filtered(
                lambda source: source.integration_origin_model == 'ab_purchase_header').mapped('integration_origin_id'))
            if any(sources.mapped('bonus')) or any(purchases.mapped('total_extra_discount')):
                raise ValidationError(_('Bonus stock and invoice discounts require an approved valuation allocation before automatic cash accounting.'))
            cost = sum(item.qty * item.unit_cost for item in allocations) * (-1 if refund else 1)
            amounts['cost_account_id'] += cost
            amounts['inventory_account_id'] -= cost
        reference = _('Sales shift closing %s') % self.id
        config._post('shift-close:%s' % self.id, self, reference, dict(amounts))
        if self.variance:
            config._post('shift-difference:%s' % self.id, self, reference,
                {'drawer_account_id': self.variance, 'difference_account_id': -self.variance})
        for transfer in self.transfer_ids.filtered(lambda record: record.direction == 'closing'):
            config._post('shift-transfer-sent:%s' % transfer.id, transfer, reference,
                {'drawer_account_id': -transfer.amount, 'transit_account_id': transfer.amount})


class CashAccountingOperation(models.TransientModel):
    _inherit = 'ab_sales_cash_operation'

    def _accept(self, session):
        result = super()._accept(session)
        shift = self.shift_id
        config = shift._accounting_configuration()
        if config and not shift.previous_id and shift.opening_amount:
            config._post('shift-opening:%s' % shift.id, shift, _('Initial drawer funding %s') % shift.id,
                {'drawer_account_id': shift.opening_amount, 'treasury_account_id': -shift.opening_amount})
        return result

    def _close(self, session):
        result = super()._close(session)
        self.shift_id._post_closing_accounts()
        return result

    def _receive(self, session):
        result = super()._receive(session)
        transfer = self.transfer_id
        config = transfer.shift_id._accounting_configuration()
        if config:
            config._post('shift-transfer-received:%s' % transfer.id, transfer, _('Treasury receipt %s') % transfer.id,
                {'treasury_account_id': transfer.amount, 'transit_account_id': -transfer.amount})
        return result

    def _review(self):
        result = super()._review()
        shift = self.shift_id
        config = shift._accounting_configuration()
        if config:
            role = 'shortage_account_id' if shift.variance < 0 else 'surplus_account_id'
            config._post('shift-finance-review:%s' % shift.id, shift, _('Finance cash difference review %s') % shift.id,
                {'difference_account_id': shift.variance, role: -shift.variance})
        return result
