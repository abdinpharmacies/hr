from odoo import fields, models


class AbProjectType(models.Model):
    _name = 'ab.project.type'
    _description = 'Development Project Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, export_string_translation=False)
    active = fields.Boolean(default=True, export_string_translation=False)

    _uniq_name = models.Constraint(
        'UNIQUE(name)',
        'Project type name must be unique.',
    )
