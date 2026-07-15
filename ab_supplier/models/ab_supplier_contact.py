from odoo import api, fields, models, _


class AbSupplierContact(models.Model):
    _name = 'ab_supplier_contact'
    _description = 'ab_supplier_contact'

    supplier_id = fields.Many2one('ab_costcenter')
    active = fields.Boolean(related='supplier_id.active')
    phone_1 = fields.Char()
