from odoo import api, fields, models, _


class AbdinEplusAbRegion(models.Model):
    _name = 'abdin_eplus_ab_region'
    _description = 'abdin_eplus_ab_region'

    name = fields.Char()
