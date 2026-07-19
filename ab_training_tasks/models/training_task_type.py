from odoo import fields, models


class TrainingTaskType(models.Model):
    _name = 'ab.training.task.type'
    _description = 'Training Task Type'
    _rec_name = 'title'
    _order = 'category_id, sequence, title'
    _check_company_auto = True

    title = fields.Char(required=True, translate=True)
    category_id = fields.Many2one(
        'ab.training.task.category',
        string='Material Category',
        required=True,
        ondelete='restrict',
        domain="[('active', '=', True)]",
    )
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='category_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    incentive_value = fields.Monetary(
        required=True,
        currency_field='currency_id',
        default=0.0,
    )

    _non_negative_incentive = models.Constraint(
        'CHECK(incentive_value >= 0)',
        'The incentive value cannot be negative.',
    )
