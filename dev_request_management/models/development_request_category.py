# -*- coding: utf-8 -*-
from odoo import fields, models


class DevelopmentRequestCategory(models.Model):
    _name = "development.request.category"
    _description = "Development Request Category"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(default=0)
    description = fields.Text()

    _name_unique = models.Constraint("UNIQUE (name)", "Category names must be unique.")
