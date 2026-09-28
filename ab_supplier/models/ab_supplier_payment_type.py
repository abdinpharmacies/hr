from odoo import fields, models


class AbSupplierPaymentType(models.Model):
    _name = 'ab_supplier_payment_type'
    _description = 'ab_supplier_payment_type'

    name = fields.Char()
