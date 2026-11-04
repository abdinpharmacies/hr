from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class EditorLayout(models.Model):
    _name = 'ab_ecommerce_editor_layout'
    _description = 'eCommerce Editor Layout'

    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, ondelete='cascade', index=True)
    tools_open = fields.Boolean(default=True)
    layers_open = fields.Boolean(default=True)
    inspector_open = fields.Boolean(default=True)
    canvas_toolbar_open = fields.Boolean(default=True)
    dark_mode = fields.Boolean(default=False)
    tools_width = fields.Integer(default=224)
    layers_height = fields.Integer(default=180)
    inspector_width = fields.Integer(default=290)

    _unique_user = models.Constraint('UNIQUE(user_id)', 'Each user can have only one editor layout.')
    _valid_sizes = models.Constraint(
        'CHECK(tools_width BETWEEN 150 AND 500 AND layers_height BETWEEN 100 AND 500 AND inspector_width BETWEEN 180 AND 520)',
        'Editor panel sizes are outside the supported range.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['user_id'] = self.env.uid
        return super().create(vals_list)

    def write(self, vals):
        if 'user_id' in vals and vals['user_id'] != self.env.uid:
            raise AccessError(_('You can only edit your own editor layout.'))
        return super().write(vals)
