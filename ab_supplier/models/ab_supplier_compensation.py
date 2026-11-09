from odoo import api, fields, models, _


class AbSupplierCompensation(models.Model):
    _name = 'ab_supplier_compensation'
    _description = 'ab_supplier_compensation'

    offers_company = fields.Many2one('ab_costcenter')
    supplier_id = fields.Many2one('ab_costcenter')
    compensation_payment_type = fields.Selection([('goods', 'Goods'),
                                                  ('cash', 'Cash')])
    compensation_type = fields.Selection([('former', 'Former'),
                                          ('later', 'Later')])
    compensation_value = fields.Float(digits=(16, 2))
    month_of_sale = fields.Date()
    month_of_deduction = fields.Date()
    notes = fields.Text()
