from odoo import api, fields, models
from odoo.tools.translate import _


class AbCustomerContact(models.Model):
    _name = 'ab_customer_contact'
    _description = 'ab_customer_contact'

    customer_id = fields.Many2one('ab_customer', index=True, required=True)
    name = fields.Char(required=True, string="phone/address", index=True)
    contact_way_id = fields.Many2one('ab_customer_contact_way',
                                     string='Contact Way')


class AbCustomerContactWay(models.Model):
    _name = 'ab_customer_contact_way'
    _description = 'ab_customer_contact_way'

    name = fields.Char(required=True)
