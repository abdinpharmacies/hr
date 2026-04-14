# -*- coding: utf-8 -*-

from odoo import models, fields


class city(models.Model):
    _name = 'ab_city'
    _description = 'city'

    name = fields.Char(required=True, index=True)
    state_id = fields.Many2one('res.country.state', string='State', required=True, index=True)
