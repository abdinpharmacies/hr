from odoo import fields, models


class AbSupplierNote(models.Model):
    _name = 'ab_supplier_note'
    _description = 'ab_supplier_note'

    name = fields.Char()

