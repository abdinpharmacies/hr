from odoo import fields, models


class CoreUIDesignToken(models.Model):
    _name = 'core_ui.design_token'
    _description = 'Core UI Design Token'
    _order = 'category_id, sequence, name'

    name = fields.Char(required=True, translate=True)
    token_name = fields.Char(required=True,
        help='CSS variable name e.g. --core-ui-color-primary')
    value = fields.Char(required=True,
        help='Token value e.g. #2563eb')
    category_id = fields.Many2one('core_ui.token_category', string='Category',
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    type = fields.Selection([
        ('color', 'Color'),
        ('typography', 'Typography'),
        ('spacing', 'Spacing'),
        ('radius', 'Border Radius'),
        ('shadow', 'Shadow'),
        ('animation', 'Animation'),
        ('icon', 'Icon'),
        ('breakpoint', 'Breakpoint'),
        ('grid', 'Grid'),
    ], default='color', required=True)
    preview_html = fields.Char(help='HTML for live preview of this token')
    active = fields.Boolean(default=True)


class CoreUITokenCategory(models.Model):
    _name = 'core_ui.token_category'
    _description = 'Core UI Token Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    icon = fields.Char(default='fa-paint-brush')
    token_ids = fields.One2many('core_ui.design_token', 'category_id',
        string='Tokens')
