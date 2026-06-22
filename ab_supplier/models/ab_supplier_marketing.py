from odoo import api, fields, models, _


class AbSuppliermarketing(models.Model):
    _name = 'ab_supplier_marketing'
    _description = 'ab_supplier_marketing'

    supplier_id = fields.Many2one('ab_costcenter')
    reason_of_discount = fields.Char()
    discount_value = fields.Float(digits=(5, 2))
    deduction_month = fields.Date()
    notes = fields.Text()
