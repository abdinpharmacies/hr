from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import AccessError


class AbCostcenterSecondAuth(models.AbstractModel):
    _name = 'ab_costcenter_second_auth'
    _inherit = ['mail.thread']
    _description = 'ab_costcenter_second_auth'

    user_code = fields.Char(store=False, readonly=False)
    password = fields.Char(store=False, readonly=False)

    def _get_cc_user(self, values):
        user_code = values.get('user_code')
        password = values.get('password')
        CC = self.env['ab_costcenter'].sudo()

        cc_user = CC.search([('code', '=', user_code)], limit=1)
        if not (user_code and cc_user.password == password):
            return False

        return cc_user
