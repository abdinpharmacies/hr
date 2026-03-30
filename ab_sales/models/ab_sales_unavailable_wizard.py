from odoo import api, fields, models
from odoo.tools.translate import _


class AbSalesUnavailableWizard(models.Model):
    _name = 'ab_sales_unavailable_wizard'
    _description = 'Reason for selling products exceeding available stock'

    header_id = fields.Many2one(
        'ab_sales_header',
        string="Sale",
        ondelete='cascade',
        required=True,
    )

    line_ids = fields.One2many(
        'ab_sales_unavailable_wizard_line',
        'wizard_id',
        string="Lines exceeding available stock",
    )

    def action_confirm(self):
        """Apply each line's reason back to the sale line and continue submit."""
        self.ensure_one()

        for w_line in self.line_ids:
            if not w_line.line_id:
                continue
            w_line.line_id.write({
                'unavailable_reason': w_line.unavailable_reason,
                'unavailable_reason_other': w_line.unavailable_reason_other,
            })

        return self.header_id.action_submit()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class AbSalesUnavailableWizardLine(models.Model):
    _name = 'ab_sales_unavailable_wizard_line'
    _description = 'Lines where requested qty exceeds available stock'

    wizard_id = fields.Many2one(
        'ab_sales_unavailable_wizard',
        string="Wizard",
        required=True,
        ondelete='cascade',
    )

    line_id = fields.Many2one(
        'ab_sales_line',
        string="Sale Line",
        required=False,
    )

    product_id = fields.Many2one(
        'ab_product',
        string="Product",
        related='line_id.product_id',
        store=False,
        readonly=True,
    )

    qty = fields.Float(
        string="Requested Qty",
        related='line_id.qty',
        readonly=True,
    )

    balance = fields.Float(
        string="Available Balance",
        related='line_id.balance',
        readonly=True,
    )

    unavailable_reason = fields.Selection([
        ('not_transferred', 'Not transferred yet from main store'),
        ('wrong_price', 'Wrong price in system'),
        ('stocktaking_error', 'Stocktaking error'),
        ('not_entered', 'Not entered by data entry yet'),
        ('promised_customer', 'Already told customer we will deliver product'),
        ('other', 'Other (please explain)'),
    ], string="Reason")

    unavailable_reason_other = fields.Char(
        string="Other (details)",
    )
