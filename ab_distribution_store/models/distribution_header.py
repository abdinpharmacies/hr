from odoo import api, fields, models


class DistributionStoreHeader(models.Model):
    _name = 'ab_distribution_store_header'
    _description = 'Distribution Store Header'
    _order = 'id desc'

    customer_name = fields.Char(required=True)
    customer_phone = fields.Char()
    customer_address = fields.Char()
    customer_note = fields.Char()
    reference = fields.Char()
    document_date = fields.Char()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    line_ids = fields.One2many('ab_distribution_store_line', 'header_id', string='Lines')
    total_qty = fields.Float(compute='_compute_totals', store=True)
    total_amount = fields.Float(compute='_compute_totals', store=True)

    @api.depends('line_ids.qty', 'line_ids.line_total')
    def _compute_totals(self):
        for rec in self:
            rec.total_qty = sum(line.qty for line in rec.line_ids)
            rec.total_amount = sum(line.line_total for line in rec.line_ids)

    def action_print_invoice(self):
        self.ensure_one()
        return self.env.ref('ab_distribution_store.action_report_distribution_store_invoice').report_action(self)
