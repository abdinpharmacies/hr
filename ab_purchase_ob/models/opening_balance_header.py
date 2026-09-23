from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class OpeningBalanceHeader(models.Model):
    _name = 'ab_purchase_ob_header'
    _description = 'opening_balance_header'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ab_inventory_process']

    store_id = fields.Many2one(
        'ab_store', domain=[('allow_purchase', '=', True)], required=True, tracking=True)
    lines_count = fields.Integer(compute='compute_totals')
    total_price = fields.Float(compute='compute_totals', digits=(12, 3))
    total_cost = fields.Float(compute='compute_totals', digits=(12, 3))
    total_tax = fields.Float(compute='compute_totals', digits=(12, 3))
    active = fields.Boolean(default=True)
    description = fields.Text()
    status = fields.Selection(
        selection=[('pending', 'Pending'), ('saved', 'Saved')],
        default='pending')
    line_ids = fields.One2many(
        comodel_name='ab_purchase_ob_line', inverse_name='header_id', required=True)

    def btn_submit_inventory(self):
        inventory = self.env['ab_inventory']
        opening_balance_details = self.line_ids
        for line in opening_balance_details:
            inventory_line = inventory.search(
                [('model_ref', '=', line._name), ('res_id', '=', line.id)]
            )
            if len(inventory_line) == 0:
                store_id = self.store_id.id
                self.inventory_write(line, line.qty, store_id)
        self.status = 'saved'

    @api.depends('line_ids', 'line_ids.qty', 'line_ids.price', 'line_ids.taxes_ids', 'line_ids.unit_cost')
    def compute_totals(self):
        for line in self:
            line.total_price = sum(rec.price * rec.qty for rec in line.line_ids)
            line.total_cost = sum(rec.unit_cost * rec.qty for rec in line.line_ids)
            line.total_tax = sum(rec.unit_taxes_value * rec.qty for rec in line.line_ids)
            line.lines_count = len(line.line_ids)
