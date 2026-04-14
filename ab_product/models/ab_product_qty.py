from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.tools import float_round


class AbProductQty(models.AbstractModel):
    _name = 'ab_product_qty'
    _description = 'ab_product_qty'

    qty_str = fields.Char(
        string='Qty',
        required=True,
        default='1',
        help='Enter arithmetic expression, e.g. 1/3, 2.5*4, 10-3, 2*1.25',
    )

    qty = fields.Float(
        string='Quantity',
        digits=(18, 4),
        compute='_compute_qty',
        store=True,
        readonly=True,
    )


    @api.depends('qty_str')
    def _compute_qty(self):
        for rec in self:
            s = (rec.qty_str or '').strip()
            if not s:
                rec.qty = 0.0
                continue
            try:
                value = safe_eval(s)
                rec.qty = float_round(float(value), precision_digits=4)
            except Exception:
                rec.qty = 0.0
