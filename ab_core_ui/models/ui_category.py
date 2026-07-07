from odoo import api, fields, models


class CoreUICategory(models.Model):
    _name = 'core_ui.category'
    _description = 'Core UI Component Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    icon = fields.Char(default='fa-folder', help='Font Awesome icon class')
    parent_id = fields.Many2one('core_ui.category', string='Parent Category')
    child_ids = fields.One2many('core_ui.category', 'parent_id', string='Subcategories')
    component_ids = fields.One2many('core_ui.component', 'category_id', string='Components')
    component_count = fields.Integer(compute='_compute_counts', store=True)
    has_children = fields.Boolean(compute='_compute_counts', store=True)

    @api.depends('component_ids', 'child_ids')
    def _compute_counts(self):
        for rec in self:
            rec.component_count = len(rec.component_ids)
            rec.has_children = bool(rec.child_ids)

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'Category name must be unique.',
    )
