from odoo import fields, models


class CoreUIPattern(models.Model):
    _name = 'core_ui.pattern'
    _description = 'Core UI UX Pattern'
    _order = 'category_id, sequence, name'

    name = fields.Char(required=True, translate=True)
    pattern_id = fields.Char(required=True, readonly=True, copy=False,
        help='Unique pattern identifier')
    category_id = fields.Many2one('core_ui.category', string='Category',
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    steps = fields.Text(translate=True, help='Step-by-step flow description')
    template_ref = fields.Char(help='QWeb template reference')
    component_ids = fields.Many2many('core_ui.component',
        relation='core_ui_pattern_component_rel',
        column1='pattern_id', column2='component_id',
        string='Used Components')
    active = fields.Boolean(default=True)
