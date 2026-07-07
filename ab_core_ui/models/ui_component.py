from odoo import api, fields, models


class CoreUIComponent(models.Model):
    _name = 'core_ui.component'
    _description = 'Core UI Component'
    _order = 'category_id, sequence, name'
    _rec_name = 'component_id'

    component_id = fields.Char(required=True, readonly=True, copy=False,
        help='Unique identifier e.g. core_ui.dialog.reject')
    name = fields.Char(required=True, translate=True)
    category_id = fields.Many2one('core_ui.category', string='Category',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    keywords = fields.Char(help='Comma-separated search keywords')
    version = fields.Char(default='1.0.0')
    status = fields.Selection([
        ('stable', 'Stable'),
        ('beta', 'Beta'),
        ('deprecated', 'Deprecated'),
        ('draft', 'Draft'),
    ], default='stable', required=True)
    author = fields.Char()
    tags = fields.Char(help='Comma-separated tags')
    is_favorite = fields.Boolean(default=False)
    usage_count = fields.Integer(default=0, help='Number of times referenced')
    preview_image = fields.Binary(string='Preview Image')
    template_ref = fields.Char(help='QWeb template reference e.g. core_ui.dialog.reject')
    when_to_use = fields.Text(translate=True)
    when_not_to_use = fields.Text(translate=True)
    accessibility_notes = fields.Text(translate=True)
    dependencies = fields.Char(help='Comma-separated module dependencies')
    slots = fields.Text(help='Available slots for this component')
    props_doc = fields.Text(string='Props Documentation')
    states_doc = fields.Text(string='States Documentation')
    has_dark_mode = fields.Boolean(default=True)
    has_light_mode = fields.Boolean(default=True)
    xml_example = fields.Text()
    owl_example = fields.Text()
    js_example = fields.Text()
    css_example = fields.Text()
    scss_example = fields.Text()
    active = fields.Boolean(default=True)
    favorite_ids = fields.Many2many('res.users',
        relation='core_ui_component_favorite_user_rel',
        column1='component_id', column2='user_id',
        string='Favorited By')

    def action_toggle_favorite(self):
        self.ensure_one()
        user = self.env.user
        if user in self.favorite_ids:
            self.favorite_ids -= user
        else:
            self.favorite_ids += user

    def action_increment_usage(self):
        self.ensure_one()
        self.usage_count += 1

    _component_id_uniq = models.Constraint(
        'UNIQUE(component_id)',
        'Component ID must be unique.',
    )
