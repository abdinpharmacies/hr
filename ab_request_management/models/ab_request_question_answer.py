from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AbRequestQuestionAnswer(models.Model):
    _name = "ab_request_question_answer"
    _description = "Request Question Answer"
    _order = "sequence, id"

    sequence = fields.Integer(related="question_id.sequence", store=True, readonly=True)
    request_id = fields.Many2one(
        "ab_request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    question_id = fields.Many2one(
        "ab_request_type_question",
        required=True,
        ondelete="restrict",
    )
    question = fields.Text(related="question_id.question", readonly=True)
    is_required = fields.Boolean(related="question_id.is_required", readonly=True)
    answer = fields.Text()

    @api.constrains("request_id", "question_id")
    def _check_request_type_question(self):
        for record in self:
            if (
                record.request_id.request_type_id
                and record.question_id.request_type_id != record.request_id.request_type_id
            ):
                raise ValidationError(_("The selected answer question must belong to the request type."))
