import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AbdinStandards(models.Model):
    _name = 'ab_fixed_asset_standards'
    _description = 'Asset standards'

    name = fields.Char(string="Standard Name")
    measure_unit = fields.Char()
    example = fields.Char()

    _ab_fixed_asset_standards_name_unique = models.Constraint('unique(name)', 'Standard Name can not be duplicated!')


class AbdinInventoryStandards(models.Model):
    _name = 'ab_fixed_asset_inventory_standards'
    _description = 'Asset standards in trans table'
    _rec_name = 'standard_id'

    standard_id = fields.Many2one('ab_fixed_asset_standards')
    measure_unit = fields.Char(related='standard_id.measure_unit', string="Measure Unit")
    example = fields.Char(related='standard_id.example', string="Example")

    standard_value = fields.Char()
    asset_id = fields.Many2one('ab_fixed_asset_assets_inventory')
