from odoo import api, fields, models


class AbRequestLink(models.Model):
    _name = "ab.request.link"
    _description = "Request Link"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "ab.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(
        string="Link Name",
        required=True,
    )
    url = fields.Char(
        string="URL",
        required=True,
    )
    sequence = fields.Integer(
        default=0,
    )

    @api.constrains("url")
    def _check_url(self):
        for record in self:
            if record.url:
                url = record.url.strip()
                if not url.startswith(("http://", "https://")):
                    raise ValidationError(
                        self.env._("The URL must start with http:// or https://")
                    )

    def action_open_url(self):
        self.ensure_one()
        if self.url:
            return {
                "type": "ir.actions.act_url",
                "url": self.url,
                "target": "new",
            }
