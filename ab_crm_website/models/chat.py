from odoo import api, fields, models, _
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from odoo.exceptions import AccessError, ValidationError


class Session(models.Model):
    _name = 'ab_crm_website_session'
    _inherit = 'ab_crm_messaging_ledger'
    _description = 'Website Live Chat Session'

    account_id = fields.Many2one('ab_crm_messaging_account', required=True, ondelete='restrict')
    session_uuid = fields.Char(required=True, index=True)
    identity_uuid = fields.Char(required=True, index=True)
    identity_kind = fields.Selection([('customer', 'Customer'), ('visitor', 'Visitor')], required=True)
    conversation_id = fields.Many2one('ab_crm_conversation', required=True, ondelete='restrict')
    ended = fields.Boolean(readonly=True)
    account_identity = fields.Char(readonly=True, index=True)
    _unique_session = models.Constraint('UNIQUE(account_id, session_uuid)', 'Website session already exists.')

    @api.constrains('account_id', 'conversation_id', 'branch_id', 'company_id')
    def _check_scope(self):
        for record in self:
            if (record.account_id.provider != 'website'
                    or record.conversation_id.channel_id != record.account_id.channel_id
                    or record.branch_id != record.account_id.branch_id
                    or record.company_id != record.account_id.company_id
                    or record.conversation_id.branch_id != record.branch_id
                    or record.conversation_id.company_id != record.company_id):
                raise ValidationError(_('Invalid website source.'))

    def write(self, values):
        if not _MUTATION.get() or set(values) - {'ended', 'account_identity'}:
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)


class ChatEvent(models.Model):
    _name = 'ab_crm_website_chat_event'
    _inherit = 'ab_crm_messaging_ledger'
    _description = 'Website Chat Event'

    account_id = fields.Many2one('ab_crm_messaging_account', required=True, ondelete='restrict')
    event_uuid = fields.Char(required=True, index=True)
    fingerprint = fields.Char(required=True)
    envelope = fields.Json(required=True)
    _unique_event = models.Constraint('UNIQUE(account_id, event_uuid)', 'Website event already exists.')

    def write(self, values):
        raise AccessError(_('Website evidence is immutable.'))
