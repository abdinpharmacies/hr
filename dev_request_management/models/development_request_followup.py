# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DevelopmentRequestFollowup(models.Model):
    _name = "development.request.followup"
    _description = "Development Request Follow-up"
    _order = "followup_date desc, id desc"

    request_id = fields.Many2one("development.request", required=True, ondelete="cascade", index=True)
    followup_date = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    summary = fields.Char(required=True)
    decision = fields.Text()
    next_action = fields.Char()
    note = fields.Html()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            body = "<b>Follow-up added</b><br/>%s" % record.summary
            if record.next_action:
                body += "<br/><b>Next action:</b> %s" % record.next_action
            if record.decision:
                body += "<br/><b>Decision:</b> %s" % record.decision
            record.request_id.message_post(body=body)
            if record.next_action:
                record.request_id.next_action = record.next_action
        return records
