from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbFixedAssetMoveWizardLine(models.Model):
    _name = 'ab_fixed_asset_move_wizard_line'
    _description = 'ab_fixed_asset_move_wizard_line'

    header_id = fields.Many2one('ab_fixed_asset_move_wizard', required=True, ondelete='restrict')
    source_id = fields.Many2one('ab_fixed_asset_inventory_line')
    name = fields.Char(compute='_compute_source_data', store=True, readonly=False)
    price = fields.Float(compute='_compute_source_data', store=True, readonly=False)
    qty = fields.Integer()
    balance = fields.Integer(related='source_id.qty', string='Balance')
    total_price = fields.Float(compute='_compute_total_price')

    @api.constrains('source_id', 'price')
    def _constrains_ab_fixed_asset_move_wizard_line(self):
        for rec in self:

            if len(rec.header_id.src_fixed_asset_ids) != 1:
                raise ValidationError(_("Choose one inventory"))

            if rec.header_id.src_fixed_asset_ids[0].asset_type == 'inventory':
                if not rec.source_id:
                    raise ValidationError(_("Source must be set!"))

            if rec.source_id and rec.price != rec.source_id.price:
                raise ValidationError(_("Price must be same as 'Source Price'"))
            if rec.source_id and rec.name != rec.source_id.name:
                raise ValidationError(_("Name must be same as 'Source Name'"))
            # if rec.source_id and rec.source_id not in rec.header_id.from_fixed_asset_line_ids:
            #     raise ValidationError(_("Source must be from Fixed Asset From Inventory Lines"))

    @api.depends('source_id')
    def _compute_source_data(self):
        for rec in self:
            if rec.source_id:
                rec.price = rec.source_id.price
                rec.name = rec.source_id.name
            else:
                rec.price = 0.0
                rec.name = ''

    @api.depends('qty', 'price')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.qty * rec.price
