# -*- coding: utf-8 -*-
from odoo import fields, models


class AbUsers(models.Model):
    _name = 'ab_users'
    _description = 'Passive User Shadow'

    name = fields.Char()
    login = fields.Char(index=True)
    active = fields.Boolean(default=True, index=True)
