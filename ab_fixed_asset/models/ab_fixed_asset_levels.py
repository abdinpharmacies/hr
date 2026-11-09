import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AbdinFirstLevel(models.Model):
    _name = 'ab_fixed_asset_first_level'
    _description = 'Assets First Level'

    name = fields.Char(string="First Level")
    account_id = fields.Many2one('ab_accounting_account_guide', domain=[('internal_type', '=', 'fixed_asset')])


class AbdinSecondLevel(models.Model):
    _name = 'ab_fixed_asset_second_level'
    _description = 'Assets Second Level'

    name = fields.Char(string="Second Level")
    first_level = fields.Many2one('ab_fixed_asset_first_level', string="First Level", required=True)


class AbdinFinalLevel(models.Model):
    _name = 'ab_fixed_asset_final_level'
    _description = 'Assets Final Level'

    name = fields.Char(string="Asset Name")
    second_level = fields.Many2one('ab_fixed_asset_second_level', string="Second Level", required=True)
    first_level = fields.Many2one(related='second_level.first_level', string="First Level")
    standards_ids = fields.Many2many('ab_fixed_asset_standards')
