from odoo import fields, models


class AbRequestTypeQuestion(models.Model):
    _name = "ab_request_type_question"
    _description = "Request Type Question"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    request_type_id = fields.Many2one(
        "ab_request_type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    question = fields.Text(required=True)
    is_required = fields.Boolean(string="Required Answer")
