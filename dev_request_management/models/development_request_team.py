# -*- coding: utf-8 -*-
from odoo import fields, models


class DevelopmentRequestTeam(models.Model):
    _name = "development.request.team"
    _description = "Development Request Team"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    lead_user_id = fields.Many2one("res.users", string="Department Lead")
    member_ids = fields.Many2many("res.users", string="Members")
    description = fields.Text()
    board_color = fields.Selection(
        [
            ("green", "Green / Product / Development"),
            ("yellow", "Yellow / Marketing / Sales"),
            ("light_blue", "Light Blue / Analytics / Data"),
            ("dark_blue", "Dark Blue / IT / Infrastructure"),
            ("red", "Red / Documentation / Support"),
            ("orange", "Orange / Executive / Strategy"),
            ("pink", "Pink / People / HR"),
        ],
        default="green",
        required=True,
    )
    color = fields.Integer(default=0)
    request_ids = fields.One2many("development.request", "responsible_team_id", string="Requests")
    request_count = fields.Integer(compute="_compute_request_count")

    def _compute_request_count(self):
        for team in self:
            team.request_count = len(team.request_ids)
