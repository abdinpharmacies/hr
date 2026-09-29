from odoo import fields, models


class PurchaseObReceiptType(models.Model):
    _name = 'ab_purchase_ob_receipt_type'
    _description = 'Non-purchase Receipt Type'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(index=True)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _code_unique = models.Constraint(
        'UNIQUE(code)',
        'Receipt type codes must be unique.',
    )
