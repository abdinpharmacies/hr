from datetime import timedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ConcurrencyError, LockError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    read_receipts_enabled = fields.Boolean(
        string='Send WhatsApp Read Receipts', default=False, groups='base.group_system'
    )


class ReadReceipt(models.Model):
    _name = 'ab_crm_read_receipt'
    _inherit = 'ab_crm_scoped'
    _description = 'WhatsApp Read Receipt'

    account_id = fields.Many2one('ab_crm_messaging_account', required=True, ondelete='restrict')
    message_id = fields.Many2one('ab_crm_message', required=True, ondelete='restrict')
    token = fields.Char(required=True, default=lambda self: str(uuid4()))
    state = fields.Selection([
        ('pending', 'Pending'), ('leased', 'Leased'),
        ('accepted', 'Accepted'), ('expired', 'Expired'), ('rejected', 'Rejected'),
    ], required=True, default='pending')
    lease = fields.Char()
    lease_until = fields.Datetime()
    available_at = fields.Datetime(default=fields.Datetime.now, required=True)
    accepted_at = fields.Datetime()
    attempts = fields.Integer(default=0)
    employee_id = fields.Integer(required=True)
    actor_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    _message_unique = models.Constraint('UNIQUE(account_id, message_id)', 'Read receipt already queued.')
    _token_unique = models.Constraint('UNIQUE(token)', 'Read receipt token must be unique.')

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Read receipts are managed by the conversation workflow.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            raise AccessError(_('Read receipts are managed by the conversation workflow.'))
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _queue_read_receipt(self, message, employee):
        self.ensure_one()
        account = self.messaging_account_id
        if (account.provider != 'whatsapp' or not account.sudo().read_receipts_enabled
                or account._queue_eligibility(self)[0]
                or account.branch_id != self.branch_id or account.company_id != self.company_id):
            return
        self.lock_for_update()
        event = self.env['ab_crm_messaging_event'].search([
            ('account_id', '=', account.id), ('message_id.conversation_id', '=', self.id),
            ('message_id.id', '<=', message.id), ('message_id.direction', '=', 'in'),
            ('message_id.historical', '=', False), ('message_id.provider_reference', '!=', False),
            ('provider_timestamp', '>=', fields.Datetime.now() - timedelta(days=30)),
            ('edit_payload', '=', False), ('message_id.reaction', '=', False),
        ], order='provider_timestamp desc, id desc', limit=1)
        if not event:
            return
        receipts = self.env['ab_crm_read_receipt'].sudo()
        if receipts.search_count([
            ('account_id', '=', account.id), ('message_id.conversation_id', '=', self.id),
            ('message_id.id', '>=', event.message_id.id),
        ], limit=1):
            return
        token = _INTERNAL.set(True)
        try:
            receipts.create({
                'account_id': account.id, 'message_id': event.message_id.id,
                'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                'employee_id': employee.id, 'actor_id': self.env.uid,
            })
        finally:
            _INTERNAL.reset(token)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _read_receipt_account(self, account_code, provider_account):
        try:
            return self._account(account_code, provider_account)
        except LockError:
            raise ConcurrencyError('Concurrent read receipt lease') from None

    @api.model
    def lease_read_receipt(self, account_code, provider_account):
        account = self._read_receipt_account(account_code, provider_account)
        if (account.provider != 'whatsapp' or not account.sudo().read_receipts_enabled
                or not account.active or not account.enabled or not account.legacy_worker_disabled
                or not account.sudo().channel_id.active):
            return False
        now = fields.Datetime.now()
        receipt = self.env['ab_crm_read_receipt'].sudo().search([
            ('account_id', '=', account.id), ('available_at', '<=', now),
            '|', ('state', '=', 'pending'), '&', ('state', '=', 'leased'), ('lease_until', '<=', now),
        ], order='id', limit=1)
        if not receipt:
            return False
        receipt.lock_for_update()
        event = self.env['ab_crm_messaging_event'].sudo().search([
            ('account_id', '=', account.id), ('message_id', '=', receipt.message_id.id),
            ('edit_payload', '=', False),
        ], limit=1)
        if not event or not event.provider_timestamp or event.provider_timestamp < now - timedelta(days=30):
            receipt._internal_write({'state': 'expired'})
            return False
        receipt._internal_write({
            'state': 'leased', 'lease': str(uuid4()), 'lease_until': now + timedelta(minutes=2),
            'attempts': receipt.attempts + 1,
        })
        return {'token': receipt.token, 'lease': receipt.lease,
                'provider': account.provider, 'provider_account': account.provider_account,
                'reference': receipt.message_id.provider_reference}

    @api.model
    def report_read_receipt(self, account_code, provider_account, token, lease, status):
        account = self._read_receipt_account(account_code, provider_account)
        receipt = self.env['ab_crm_read_receipt'].sudo().search([
            ('account_id', '=', account.id), ('token', '=', token),
        ], limit=1)
        if not receipt or receipt.branch_id != account.branch_id or receipt.company_id != account.company_id:
            raise AccessError(_('The messaging account is not authorized.'))
        receipt.lock_for_update()
        if status not in ('accepted', 'retry', 'rejected'):
            raise ValidationError(_('Invalid read receipt result.'))
        if receipt.state == 'accepted' and status == 'accepted':
            return True
        if receipt.state != 'leased' or receipt.lease != lease or receipt.lease_until <= fields.Datetime.now():
            raise AccessError(_('The outgoing lease has expired.'))
        values = {'state': 'pending' if status == 'retry' else status, 'lease': False}
        if status == 'accepted':
            values['accepted_at'] = fields.Datetime.now()
        elif status == 'retry':
            values['available_at'] = fields.Datetime.now() + timedelta(seconds=min(3600, 30 * 2 ** min(receipt.attempts, 7)))
        receipt._internal_write(values)
        return True
