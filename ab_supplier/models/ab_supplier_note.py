from odoo import api, fields, models
from odoo.tools.translate import _


class AbSupplierNote(models.Model):
    _name = 'ab_supplier_note'
    _description = 'ab_supplier_note'

    name = fields.Char()

