from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError


class AbdinUom(models.Model):
    _name = 'ab_uom'
    _description = 'Abdin Unit Of Measure'
    _order = 'unit_size'

    type_id = fields.Many2one('ab_uom_type', required=False)
    unit_no = fields.Integer(required=False)
    unit_size = fields.Selection(selection=[(
        'large', 'Large'), ('medium', 'Medium'), ('small', 'Small')], required=False)

    @api.depends_context('uom_only_type')
    @api.depends('type_id.name', 'unit_no', 'unit_size')
    def _compute_display_name(self):
        for rec in self:
            if self.env.context.get('uom_only_type', False):
                unit_size_selection = {
                    'large': 'L', 'medium': 'M', 'small': 'S'}
                rec.display_name = f"{rec.type_id.name} ({unit_size_selection[rec.unit_size]})"
            else:
                rec.display_name = f"{rec.unit_no} {rec.type_id.name}"

    @api.model
    def _search_display_name(self, operator, value):
        domain = []
        if value or operator != 'ilike':
            for part in (value or '').split(" "):
                domain += ['|', ('type_id', operator, part), ('unit_no', operator, part)]
        return domain


class AbdinUomType(models.Model):
    _name = 'ab_uom_type'
    _description = 'Abdin Uom Type'

    name = fields.Char(required=False)
