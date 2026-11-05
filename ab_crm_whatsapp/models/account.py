from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    provider = fields.Selection(
        selection_add=[('whatsapp', 'WhatsApp')],
        ondelete={'whatsapp': lambda records: records._prevent_provider_removal()},
    )

    def _eligible(self, conversation, body):
        deadline = super()._eligible(conversation, body)
        if self.provider == 'whatsapp':
            deadline = (
                conversation.messaging_last_inbound
                and conversation.messaging_last_inbound + timedelta(hours=24)
            )
            if not deadline or deadline <= fields.Datetime.now() + timedelta(
                seconds=30
            ):
                raise UserError(
                    _(
                        'WhatsApp replies require an incoming customer message within the last 24 hours.'
                    )
                )
        return deadline

    def _status_allowed(self, status):
        return (
            self.provider == 'whatsapp'
            and status in ('accepted', 'delivered', 'read', 'failed', 'review')
        ) or super()._status_allowed(status)
