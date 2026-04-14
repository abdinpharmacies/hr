from odoo import api, fields, models, _


class MailChannelPartner(models.Model):
    _name = 'discuss.channel.member'
    _inherit = 'discuss.channel.member'

    is_cc = fields.Boolean(default=True)
