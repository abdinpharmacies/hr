from odoo import api, fields, models, _


class AbdinProductBarcode(models.Model):
    _name = 'ab_product_barcode'
    _description = 'Abdin Product Barcode'

    name = fields.Char(required=True, index=True)
    product_ids = fields.Many2many(comodel_name='ab_product',
                                   relation='ab_product_barcode_rel',
                                   column2='product_id',
                                   column1='barcode_id')

    eplus_serial = fields.Integer(index=True)

    last_update_date = fields.Datetime(index=True)
