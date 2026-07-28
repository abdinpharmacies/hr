from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import AccessError


class CustomerInherit(models.Model):
    _name = 'ab_customer'
    _inherit = ['ab_costcenter_second_auth', 'ab_customer', ]

    eplus_serial = fields.Integer(index=True, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)

    eplus_create_date = fields.Datetime()
