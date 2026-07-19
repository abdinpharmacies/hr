from odoo import fields, models


class TrainingTaskCategory(models.Model):
    _name = 'ab.training.task.category'
    _description = 'Training Task Category'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    task_type_ids = fields.One2many(
        'ab.training.task.type',
        'category_id',
        string='Task Types',
    )
