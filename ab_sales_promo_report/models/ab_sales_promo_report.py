"""Recorded promotions on local callcenter invoices; no external database reads."""
from datetime import datetime, time, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PromotionReportLine(models.Model):
    _name = 'ab_sales_promo_report_line'
    _description = 'Recorded Callcenter Promotion'
    _order = 'invoice_date desc, invoice_id desc, id'

    invoice_id = fields.Many2one('ab_sales_header', string='Invoice', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='invoice_id.store_id', store=True)
    invoice_date = fields.Date(string='Invoice Date', required=True)
    promo_id = fields.Many2one('ab_promo_program', string='Promotion', required=True, ondelete='restrict')
    promotion_ownership = fields.Selection(related='promo_id.promotion_ownership', string='Promotion Ownership')
    product_id = fields.Many2one('ab_product', string='Product', required=True, ondelete='restrict')
    qty = fields.Float(string='Quantity')
    price = fields.Float(string='Price')
    total_price = fields.Float(string='Line Gross Total')
    promo_discount = fields.Float(string='Recorded Invoice Promotion Discount', aggregator=False)
    total_invoice_after_promo = fields.Float(string='Recorded Invoice Total After Promotion', aggregator=False)


class PromotionReportWizard(models.TransientModel):
    _name = 'ab_sales_promo_report_wizard'
    _description = 'Load Recorded Callcenter Promotions'

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    store_ids = fields.Many2many('ab_store', string='Branches')
    product_ids = fields.Many2many('ab_product', string='Products')
    promo_ids = fields.Many2many('ab_promo_program', string='Promotions')
    replace_existing = fields.Boolean(string='Replace My Report Rows', default=True)

    def action_load_report(self):
        self.ensure_one()
        self.check_access('read')
        if self.date_from > self.date_to:
            raise UserError(_('Date From must be before Date To.'))
        self.store_ids.check_access('read')
        domain = (fields.Domain('is_callcenter_order', '=', True)
                  & fields.Domain('status', '=', 'saved')
                  & fields.Domain('create_date', '>=', datetime.combine(self.date_from, time.min))
                  & fields.Domain('create_date', '<', datetime.combine(self.date_to + timedelta(days=1), time.min)))
        if self.store_ids:
            domain &= fields.Domain('store_id', 'in', self.store_ids.ids)
        headers = self.env['ab_sales_header'].search(domain, order='id')
        Report = self.env['ab_sales_promo_report_line']
        values = []
        for header in headers:
            snapshot = header.callcenter_promo_snapshot or {}
            programs = snapshot.get('program_ids', [])
            for program in self.env['ab_promo_program'].browse(programs).exists():
                program.check_access('read')
                if self.promo_ids and program not in self.promo_ids:
                    continue
                # Product selection filters output only; recorded invoice totals remain intact.
                for line in header.line_ids:
                    if self.product_ids and line.product_id not in self.product_ids:
                        continue
                    values.append({'invoice_id': header.id, 'invoice_date': header.create_date.date(),
                        'promo_id': program.id, 'product_id': line.product_id.id,
                        'qty': line.qty, 'price': line.sell_price, 'total_price': line.qty * line.sell_price,
                        'promo_discount': snapshot.get('discount', 0),
                        'total_invoice_after_promo': snapshot.get('net', 0)})
        if self.replace_existing:
            Report.search(fields.Domain('create_uid', '=', self.env.uid)
                          & fields.Domain('invoice_date', '>=', self.date_from)
                          & fields.Domain('invoice_date', '<=', self.date_to)).unlink()
        records = Report.create(values)
        return {'type': 'ir.actions.act_window', 'name': _('Recorded Callcenter Promotions'),
                'res_model': Report._name, 'view_mode': 'list,pivot,graph',
                'domain': [('id', 'in', records.ids)]}
