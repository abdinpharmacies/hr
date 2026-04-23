# -*- coding: utf-8 -*-
from odoo import fields, models


class DevelopmentRequestStage(models.Model):
    _name = "development.request.stage"
    _description = "Development Request Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("in_progress", "In Progress"),
            ("testing", "Testing"),
            ("done", "Done"),
            ("rejected", "Rejected"),
        ],
        required=True,
    )
    sequence = fields.Integer(default=10)
    fold = fields.Boolean()
    description = fields.Text()
    is_closed = fields.Boolean(
        compute="_compute_is_closed",
        store=True,
    )

    _stage_code_unique = models.Constraint("UNIQUE (code)", "Each stage code must be unique.")
    _stage_name_unique = models.Constraint("UNIQUE (name)", "Each stage name must be unique.")

    def _compute_is_closed(self):
        for stage in self:
            stage.is_closed = stage.code in ("done", "rejected")
