# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from .extra_functions import get_modified_name


class Region(models.Model):
    _name = 'ab_hr_region'
    _description = 'ab_hr_region'
    name = fields.Char(required=True)

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return ['|', ('name', operator, value), ('name', operator, mod_name)]
