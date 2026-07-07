from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    core_ui_animation_speed = fields.Selection([
        ('slow', 'Slow'),
        ('normal', 'Normal'),
        ('fast', 'Fast'),
    ], default='normal', string='Animation Speed',
        config_parameter='core_ui.animation_speed')

    core_ui_theme = fields.Selection([
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System Default'),
    ], default='system', string='Theme',
        config_parameter='core_ui.theme')

    core_ui_dev_mode = fields.Boolean(string='Developer Mode',
        config_parameter='core_ui.dev_mode')

    core_ui_show_preview = fields.Boolean(string='Show Live Previews',
        default=True, config_parameter='core_ui.show_preview')

    def action_open_component_gallery(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'core_ui.gallery',
            'target': 'new',
        }

    def action_launch_workspace(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'core_ui.workspace',
            'target': 'new',
        }
