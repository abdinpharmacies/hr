import json
import re
from contextvars import ContextVar
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL

_MUTATION = ContextVar('ab_messaging_mutation', default=False)
_EDIT = ContextVar('ab_messaging_edit', default=False)
ERRORS = [
    ('none', 'No error'),
    ('media', 'Media validation failed before sending'),
    ('rejected', 'Provider rejected the message'),
    ('rate_limit', 'Provider rate limit reached'),
    ('ambiguous', 'Sending outcome is uncertain; review required'),
    ('window', 'WhatsApp reply window has expired'),
    ('unavailable', 'Provider temporarily unavailable'),
]


class Account(models.Model):
    _name = 'ab_crm_messaging_account'
    _inherit = 'ab_crm_scoped'
    _description = 'Messaging Account'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    provider = fields.Selection([], required=True)
    provider_account = fields.Char(required=True)
    channel_id = fields.Many2one(
        'ab_crm_channel', required=True, ondelete='restrict', check_company=True
    )
    service_user_id = fields.Many2one(
        'res.users', required=True, ondelete='restrict', check_company=True
    )
    active = fields.Boolean(default=True)
    enabled = fields.Boolean(string='Messaging Enabled', default=False)
    outgoing_enabled = fields.Boolean(default=False, string='Outgoing Sending Enabled')
    contact_automation = fields.Boolean(
        default=False, string='Automatic Contact Request'
    )
    legacy_worker_disabled = fields.Boolean(
        string='Previous Worker Disabled', default=False
    )
    _code_unique = models.Constraint('UNIQUE(code)', 'Account code must be unique.')
    _channel_unique = models.Constraint(
        'UNIQUE(channel_id)', 'A channel can have only one messaging account.'
    )
    _provider_unique = models.Constraint(
        'UNIQUE(provider, provider_account)', 'Provider account must be unique.'
    )

    @api.constrains(
        'channel_id',
        'branch_id',
        'company_id',
        'provider',
        'service_user_id',
        'enabled',
        'legacy_worker_disabled',
    )
    def _check_mapping(self):
        for record in self:
            if (
                record.channel_id.branch_id != record.branch_id
                or record.channel_id.company_id != record.company_id
                or record.channel_id.provider != record.provider
            ):
                raise ValidationError(
                    _(
                        'Account and channel must have the same provider, branch and company.'
                    )
                )
            user = record.service_user_id
            if (
                not user.has_group('ab_crm_messaging.group_service')
                or user.has_group('ab_crm_core.group_user')
                or user.has_group('base.group_system')
                or user not in record.branch_id.with_context(active_test=False).user_ids
                or (record.enabled and not user.active)
                or record.company_id not in user.company_ids
            ):
                raise ValidationError(
                    _(
                        'Assign a messaging service user authorized for this branch and company.'
                    )
                )
            if record.enabled and not record.legacy_worker_disabled:
                raise ValidationError(
                    _('Disable the previous gateway worker before enabling messaging.')
                )

    def write(self, values):
        if set(values) & {'code', 'provider', 'provider_account', 'channel_id'}:
            raise UserError(
                _('Account mapping is immutable. Archive the account to replace it.')
            )
        return super().write(values)

    def _queue_eligibility(self, conversation):
        self.ensure_one()
        if (
            not self.active
            or not self.enabled
            or not self.channel_id.active
            or not self.legacy_worker_disabled
        ):
            return 'account_disabled', _('Messaging is disabled for this account.')
        if conversation.channel_id != self.channel_id or not conversation.external_key:
            return 'invalid_destination', _('Invalid messaging destination.')
        return False, False

    def _valid_incoming_identity(self, value):
        return self.provider in ('telegram', 'whatsapp') and value.isascii() and value.isdecimal()

    def _eligible(self, conversation, body):
        code, reason = self._queue_eligibility(conversation)
        if code:
            raise UserError(reason)
        if not body or len(body) > 4096:
            raise UserError(_('Replies must contain between 1 and 4096 characters.'))
        return False

    def _eligible_message(self, message):
        return self._eligible(message.conversation_id, message.body)

    def _prevent_provider_removal(self):
        if self:
            raise UserError(
                _('Provider addons cannot be removed while messaging accounts exist.')
            )

    def _status_allowed(self, status):
        return status in ('accepted', 'failed', 'review')


class Channel(models.Model):
    _inherit = 'ab_crm_channel'

    def write(self, values):
        if 'provider' in values and self.env[
            'ab_crm_messaging_account'
        ].sudo().with_context(active_test=False).search_count(
            [('channel_id', 'in', self.ids)]
        ):
            raise UserError(
                _('The provider of a configured messaging channel cannot be changed.')
            )
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    messaging_last_inbound = fields.Datetime(readonly=True, copy=False)
    messaging_account_id = fields.Many2one(
        'ab_crm_messaging_account', compute='_compute_messaging_account'
    )
    messaging_enabled = fields.Boolean(compute='_compute_messaging_account')

    @api.depends('channel_id')
    def _compute_messaging_account(self):
        accounts = (
            self.env['ab_crm_messaging_account']
            .with_context(active_test=False)
            .search([('channel_id', 'in', self.channel_id.ids)])
        )
        mapping = {account.channel_id.id: account for account in accounts}
        for record in self:
            record.messaging_account_id = mapping.get(record.channel_id.id)
            record.messaging_enabled = record.messaging_account_id.enabled

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get():
            if any('messaging_last_inbound' in values for values in values_list):
                raise AccessError(_('Messaging evidence is managed by the gateway.'))
            values_list = [
                dict(values, messaging_last_inbound=False) for values in values_list
            ]
        return super().create(values_list)

    def write(self, values):
        if 'messaging_last_inbound' in values and not _MUTATION.get():
            raise AccessError(_('Messaging evidence is managed by the gateway.'))
        if set(values) & {'channel_id', 'external_key'}:
            accounts = (
                self.env['ab_crm_messaging_account']
                .sudo()
                .with_context(active_test=False)
                .search([('channel_id', 'in', self.channel_id.ids)])
            )
            if accounts:
                raise UserError(_('Messaging destinations cannot be changed.'))
        return super().write(values)


class Message(models.Model):
    _inherit = 'ab_crm_message'

    historical = fields.Boolean(string='Historical Unverified Import', readonly=True, copy=False, index=True)
    original_timestamp = fields.Datetime(string='Original Timestamp', readonly=True, copy=False)

    timeline_at = fields.Datetime(string='Timeline Timestamp', compute='_compute_timeline_at', store=True, index=True)

    @api.depends('original_timestamp', 'create_date')
    def _compute_timeline_at(self):
        for record in self:
            record.timeline_at = record.original_timestamp or record.create_date

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get() and any(
            {'historical', 'original_timestamp', 'timeline_at'} & values.keys() for values in values_list
        ):
            raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        return super().create(values_list)

    messaging_operation_ids = fields.One2many(
        'ab_crm_messaging_operation', 'message_id', readonly=True
    )

    def action_approve(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        mapped = []
        for message in self:
            if message.conversation_id.channel_id.provider not in (
                'whatsapp',
                'telegram',
            ):
                continue
            account = (
                self.env['ab_crm_messaging_account']
                .with_context(active_test=False)
                .search(
                    [('channel_id', '=', message.conversation_id.channel_id.id)],
                    limit=1,
                )
            )
            if not account:
                raise UserError(
                    _('Configure a messaging account before approving replies.')
                )
            account._authorize('read')
            account.lock_for_update()
            deadline = account._eligible_message(message)
            mapped.append((message, account, deadline))
        result = super().action_approve()
        for message, account, deadline in mapped:
            token = _MUTATION.set(True)
            try:
                self.env['ab_crm_messaging_operation'].sudo().with_context(
                    {}, allowed_company_ids=message.company_id.ids
                ).create(
                    {
                        'account_id': account.id,
                        'message_id': message.id,
                        'body': message.body,
                        'content': message._outgoing_extra(),
                        'destination': message.conversation_id.external_key,
                        'expires_at': deadline,
                        'branch_id': message.branch_id.id,
                        'company_id': message.company_id.id,
                        'approved_by': self.env.uid,
                        'approved_at': message.approved_at,
                    }
                )
            finally:
                _MUTATION.reset(token)
            message._internal_write({'delivery_state': 'unknown'})
        return result


class Ledger(models.AbstractModel):
    _name = 'ab_crm_messaging_ledger'
    _inherit = 'ab_crm_scoped'
    _description = 'Messaging Ledger'

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get():
            raise AccessError(_('Messaging evidence is managed by the gateway.'))
        return super().create(values_list)

    def write(self, values):
        if not _MUTATION.get():
            raise AccessError(_('Messaging evidence is managed by the gateway.'))
        return super().write(values)

    def _change(self, values):
        token = _MUTATION.set(True)
        try:
            return self.sudo().write(values)
        finally:
            _MUTATION.reset(token)


class Event(models.Model):
    _name = 'ab_crm_messaging_event'
    _inherit = 'ab_crm_messaging_ledger'
    _description = 'Incoming Messaging Event'
    _rec_name = 'event_key'

    account_id = fields.Many2one(
        'ab_crm_messaging_account', required=True, ondelete='restrict'
    )
    event_key = fields.Char(required=True)
    fingerprint = fields.Char(required=True)
    provider_timestamp = fields.Datetime(readonly=True)
    message_id = fields.Many2one('ab_crm_message', ondelete='restrict')
    _event_unique = models.Constraint(
        'UNIQUE(account_id, event_key)', 'This event was already received.'
    )


class Operation(models.Model):
    _name = 'ab_crm_messaging_operation'
    _inherit = 'ab_crm_messaging_ledger'
    _description = 'Outgoing Messaging Operation'
    _rec_name = 'token'

    account_id = fields.Many2one(
        'ab_crm_messaging_account', required=True, ondelete='restrict'
    )
    message_id = fields.Many2one('ab_crm_message', required=True, ondelete='restrict')
    token = fields.Char(required=True, default=lambda self: str(uuid4()), copy=False)
    body = fields.Text(required=True)
    destination = fields.Char(required=True)
    approved_by = fields.Many2one('res.users', required=True)
    approved_at = fields.Datetime(required=True)
    expires_at = fields.Datetime()
    attempt = fields.Integer(default=1, required=True)
    state = fields.Selection(
        [
            ('queued', 'Queued'),
            ('leased', 'Leased'),
            ('received', 'Gateway Received'),
            ('accepted', 'Provider Accepted'),
            ('delivered', 'Delivered'),
            ('read', 'Read'),
            ('failed', 'Failed'),
            ('review', 'Needs Review'),
            ('resolved', 'Review Closed'),
            ('cancelled', 'Cancelled'),
        ],
        default='queued',
        required=True,
    )
    lease_token = fields.Char(groups='ab_crm_messaging.group_service')
    lease_until = fields.Datetime()
    receipt = fields.Char()
    provider_reference = fields.Char(index=True)
    error_code = fields.Selection(ERRORS, default='none', required=True)
    retryable = fields.Boolean()
    review_note = fields.Text()
    reviewed_by = fields.Many2one('res.users')
    reviewed_at = fields.Datetime()
    history = fields.Json(default=list)
    _message_unique = models.Constraint(
        'UNIQUE(message_id)', 'A message can have only one outgoing operation.'
    )
    _token_unique = models.Constraint(
        'UNIQUE(token)', 'Operation token must be unique.'
    )

    def action_cancel_unsent(self, reason):
        self._staff_action()
        self._authorize('read')
        if not isinstance(reason, str) or not reason.strip():
            raise UserError(_('Provide a cancellation reason.'))
        for record in self:
            record.account_id.lock_for_update()
            record.lock_for_update()
            record.invalidate_recordset()
            if (
                record.state != 'queued'
                or record.sudo().lease_token
                or record.receipt
                or record.sudo().provider_reference
                or record.attempt != 1
                or record.sudo().history
            ):
                raise UserError(
                    _('Only an unsent, never-leased operation can be cancelled.')
                )
            record._change(
                {
                    'state': 'cancelled',
                    'history': [
                        {
                            'action': 'cancelled',
                            'actor': self.env.uid,
                            'at': fields.Datetime.to_string(fields.Datetime.now()),
                            'reason': reason[:2000],
                        }
                    ],
                }
            )
        return True

    def action_retry(self):
        self._staff_action()
        self._authorize('read')
        self.lock_for_update()
        for record in self:
            if record.state != 'failed' or not record.retryable:
                raise UserError(
                    _('Only a definitively rejected retryable send can be retried.')
                )
            deadline = record.account_id._eligible_message(record.message_id)
            record._change(
                {
                    'state': 'queued',
                    'attempt': record.attempt + 1,
                    'receipt': False,
                    'lease_token': False,
                    'lease_until': False,
                    'retryable': False,
                    'expires_at': deadline,
                    'error_code': 'none',
                    'history': (record.sudo().history or [])
                    + [
                        {
                            'action': 'retry',
                            'actor': self.env.uid,
                            'at': fields.Datetime.to_string(fields.Datetime.now()),
                        }
                    ],
                }
            )
        return True

    def action_close_review(self, note=None):
        self._staff_action()
        self._authorize('read')
        self.lock_for_update()
        for record in self:
            review_note = note or record.review_note
            if (
                record.state != 'review'
                or not isinstance(review_note, str)
                or not review_note.strip()
            ):
                raise UserError(
                    _('Enter a review note before closing an uncertain send.')
                )
            record._change(
                {
                    'state': 'resolved',
                    'review_note': review_note[:2000],
                    'reviewed_by': self.env.uid,
                    'reviewed_at': fields.Datetime.now(),
                }
            )
        return True

    def write(self, values):
        if not _MUTATION.get() and set(values) == {'review_note'}:
            self._staff_action()
            self._authorize('read')
            if any(record.state != 'review' for record in self):
                raise UserError(
                    _('Review notes can only be edited while a send needs review.')
                )
            return self._change(values)
        return super().write(values)


class MessagingAPI(models.AbstractModel):
    _name = 'ab_crm_messaging_api'
    _description = 'Messaging Gateway API'

    def _account(self, account_code, provider_account):
        user = self.env.user
        if (
            not user.has_group('ab_crm_messaging.group_service')
            or user.has_group('ab_crm_core.group_user')
            or user.has_group('base.group_system')
        ):
            raise AccessError(
                _('Only a dedicated messaging service account can use this API.')
            )
        account = (
            self.env['ab_crm_messaging_account']
            .with_context(active_test=False)
            .search([('code', '=', account_code)], limit=1)
        )
        if (
            not account
            or account.service_user_id != user
            or account.provider_account != provider_account
            or account.company_id not in self.env.companies
            or user not in account.branch_id.sudo().user_ids
        ):
            raise AccessError(_('The messaging account is not authorized.'))
        account.lock_for_update()
        return account

    def _operation(self, account, token, attempt):
        operation = (
            self.env['ab_crm_messaging_operation']
            .sudo()
            .search(
                [
                    ('account_id', '=', account.id),
                    ('token', '=', token),
                    ('attempt', '=', attempt),
                ],
                limit=1,
            )
        )
        if not operation:
            raise AccessError(_('The outgoing operation is not authorized.'))
        operation.lock_for_update()
        return operation

    @api.model
    def receive_event(self, account_code, provider_account, event):
        account = self._account(account_code, provider_account)
        if (
            not account.active
            or not account.enabled
            or not account.channel_id.sudo().active
        ):
            raise UserError(_('Messaging is disabled for this account.'))
        if not isinstance(event, dict) or set(event) - {
            'contact',
            'profile',
            'media',
            'reply_reference',
            'reaction',
            'location',
            'edit',
        } != {
            'id',
            'sender',
            'body',
            'timestamp',
            'unsupported',
            'source_digest',
        }:
            raise ValidationError(_('Invalid incoming messaging event.'))
        if (
            not all(
                isinstance(event[k], str) and 0 < len(event[k]) <= 256
                for k in ('id', 'sender')
            )
            or not isinstance(event['body'], str)
            or len(event['body']) > 20000
            or not isinstance(event['source_digest'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', event['source_digest'])
            or not account._valid_incoming_identity(event['sender'])
            or type(event['unsupported']) is not bool
            or not (event['body'] or event['unsupported'])
        ):
            raise ValidationError(_('Invalid incoming messaging event.'))
        try:
            timestamp = fields.Datetime.to_datetime(event['timestamp'])
        except (ValueError, TypeError):
            timestamp = None
        if not timestamp or timestamp > fields.Datetime.now() + timedelta(minutes=5):
            raise ValidationError(_('Invalid incoming messaging event.'))
        timestamp = min(timestamp, fields.Datetime.now())
        location = None
        if 'location' in event:
            from .location import validate_location
            location = validate_location(event['location'])
            if event['unsupported'] or event.get('media') or event.get('contact') or event.get('reaction'):
                raise ValidationError(_('Invalid incoming messaging event.'))
            location['timestamp'] = fields.Datetime.to_string(timestamp)
        fingerprint = sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        clean_context = {
            'allowed_company_ids': account.company_id.ids,
            'lang': self.env.lang,
        }
        if 'edit' in event:
            return self._receive_edit(account, event, timestamp, location, fingerprint, clean_context)
        ledger = self.env['ab_crm_messaging_event'].sudo().with_context(clean_context)
        existing = ledger.search(
            [('account_id', '=', account.id), ('event_key', '=', event['id'])], limit=1
        )
        if existing:
            if existing.fingerprint != fingerprint:
                raise ValidationError(
                    _('An event identity cannot be reused with different content.')
                )
            return {'message_id': existing.message_id.id}
        scope = {'branch_id': account.branch_id.id, 'company_id': account.company_id.id}
        conversation = (
            self.env['ab_crm_conversation']
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ('channel_id', '=', account.channel_id.id),
                    ('external_key', '=', event['sender']),
                ],
                limit=1,
            )
        )
        mutation = _MUTATION.set(True)
        internal = _INTERNAL.set(True)
        try:
            if not conversation:
                identity = (
                    self.env['ab_crm_identity']
                    .sudo()
                    .search(
                        [
                            ('channel_id', '=', account.channel_id.id),
                            ('external_key', '=', event['sender']),
                            ('branch_id', '=', account.branch_id.id),
                            ('company_id', '=', account.company_id.id),
                        ],
                        limit=1,
                    )
                )
                conversation = (
                    self.env['ab_crm_conversation']
                    .sudo()
                    .with_context(clean_context)
                    .create(
                        dict(
                            scope,
                            name=event['sender'],
                            external_key=event['sender'],
                            channel_id=account.channel_id.id,
                            customer_id=identity.customer_id.id,
                        )
                    )
                )
            body = (
                _('Unsupported attachment received. Staff review is required.')
                if event['unsupported']
                else event['body']
            )
            if location:
                body = '\n'.join(filter(None, [
                    _('Location snapshot') if location['is_live_snapshot'] else _('Location'),
                    location['name'], location['address'],
                    f"{location['latitude']}, {location['longitude']}",
                ]))
            message = (
                self.env['ab_crm_message']
                .sudo()
                .with_context(clean_context)
                .create(
                    dict(
                        scope,
                        conversation_id=conversation.id,
                        body=body,
                        location_snapshot=location or False,
                        direction='in',
                        original_timestamp=timestamp,
                        delivery_state='sent',
                        approved_by=False,
                        approved_at=False,
                        token=str(uuid4()),
                        provider_reference=(
                            event['id'].split(':')[-1]
                            if account.provider == 'telegram'
                            else event['id']
                        ),
                        provider_event=sha256(
                            json.dumps([account.code, event['id']]).encode()
                        ).hexdigest(),
                    )
                )
            )
            if (
                not conversation.messaging_last_inbound
                or timestamp > conversation.messaging_last_inbound
            ):
                conversation.write({'messaging_last_inbound': timestamp})
            self._receive_event_extra(account, event, message)
            ledger.create(
                dict(
                    scope,
                    account_id=account.id,
                    event_key=event['id'],
                    fingerprint=fingerprint,
                    provider_timestamp=timestamp,
                    message_id=message.id,
                    media_id=message.media_ids[:1].id,
                )
            )
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        return {'message_id': message.id}

    def _receive_event_extra(self, account, event, message):
        if event.get('contact'):
            raise ValidationError(
                _('Contact events require a supported provider addon.')
            )

    @api.model
    def lease_outgoing(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if (
            not account.active
            or not account.enabled
            or not account.channel_id.sudo().active
            or not account.legacy_worker_disabled
        ):
            return False
        now = fields.Datetime.now()
        operation = (
            self.env['ab_crm_messaging_operation']
            .sudo()
            .search(
                [
                    ('account_id', '=', account.id),
                    '|',
                    ('state', '=', 'queued'),
                    '&',
                    ('state', '=', 'leased'),
                    ('lease_until', '<=', now),
                ],
                order='id',
                limit=1,
            )
        )
        if not operation:
            return False
        operation._change(
            {
                'state': 'leased',
                'lease_token': str(uuid4()),
                'lease_until': now + timedelta(minutes=2),
            }
        )
        return {
            'token': operation.token,
            'attempt': operation.attempt,
            'lease': operation.lease_token,
            'provider': account.provider,
            'provider_account': account.provider_account,
            'body': operation.body,
            **(operation.content or {}),
            'destination': operation.destination,
            'expires_at': fields.Datetime.to_string(operation.expires_at),
        }

    @api.model
    def acknowledge_receipt(
        self, account_code, provider_account, token, attempt, lease, receipt
    ):
        account = self._account(account_code, provider_account)
        operation = self._operation(account, token, attempt)
        if not isinstance(receipt, str) or not 1 <= len(receipt) <= 128:
            raise ValidationError(_('Invalid durable receipt.'))
        if operation.receipt:
            if operation.receipt != receipt:
                raise ValidationError(_('Invalid durable receipt.'))
            return True
        if (
            operation.state != 'leased'
            or operation.lease_token != lease
            or operation.lease_until <= fields.Datetime.now()
        ):
            raise UserError(_('The outgoing lease has expired.'))
        operation._change({'receipt': receipt, 'state': 'received'})
        return True

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        account = self._account(account_code, provider_account)
        operation = self._operation(account, token, attempt)
        return bool(
            account.active
            and account.enabled
            and account.legacy_worker_disabled
            and account.channel_id.sudo().active
            and operation.receipt == receipt
            and operation.state == 'received'
        )

    @api.model
    def report_delivery(
        self,
        account_code,
        provider_account,
        token,
        attempt,
        receipt,
        status,
        reference='',
        error='none',
    ):
        account = self._account(account_code, provider_account)
        operation = self._operation(account, token, attempt)
        if (
            not operation.receipt
            or operation.receipt != receipt
            or status not in ('accepted', 'failed', 'review')
        ):
            raise ValidationError(_('Invalid delivery evidence.'))
        self._apply_status(account, operation, status, reference, error)
        return True

    def _apply_status(self, account, operation, status, reference, error):
        if (
            not account._status_allowed(status)
            or error not in dict(ERRORS)
            or not isinstance(reference, str)
            or len(reference) > 256
        ):
            raise ValidationError(_('Invalid delivery evidence.'))
        if status in ('accepted', 'delivered', 'read') and not reference:
            raise ValidationError(_('Invalid delivery evidence.'))
        if (
            reference
            and operation.provider_reference
            and reference != operation.provider_reference
        ):
            raise ValidationError(_('Invalid delivery evidence.'))
        ranks = {'accepted': 1, 'delivered': 2, 'read': 3}
        if (
            operation.state == status
            and operation.provider_reference == (reference or False)
            and operation.error_code == error
        ):
            return
        if operation.state in ('delivered', 'read') and (
            status not in ranks or ranks[status] <= ranks[operation.state]
        ):
            return
        if operation.state == 'accepted' and (
            status in ('accepted', 'review')
            or (status == 'failed' and (account.provider != 'whatsapp' or not reference))
        ):
            return
        if (
            operation.state == 'failed'
            and operation.provider_reference
            and status in ('accepted', 'failed', 'review')
        ):
            return
        values = {
            'state': status,
            'error_code': error,
            'retryable': status == 'failed'
            and error in ('rate_limit', 'unavailable')
            and not (reference or operation.provider_reference),
            'history': (operation.history or [])
            + [
                {
                    'status': status,
                    'reference': reference,
                    'error': error,
                    'actor': self.env.uid,
                    'at': fields.Datetime.to_string(fields.Datetime.now()),
                }
            ],
        }
        if reference:
            values['provider_reference'] = reference
        operation._change(values)
        if status in ranks:
            operation.message_id._internal_write(
                {'delivery_state': 'sent', 'provider_reference': reference}
            )

    @api.model
    def receive_status(
        self, account_code, provider_account, reference, destination, status
    ):
        account = self._account(account_code, provider_account)
        if status not in (
            'accepted',
            'delivered',
            'read',
            'failed',
        ) or not account._status_allowed(status):
            raise ValidationError(_('Invalid delivery evidence.'))
        operation = (
            self.env['ab_crm_messaging_operation']
            .sudo()
            .search(
                [
                    ('account_id', '=', account.id),
                    ('provider_reference', '=', reference),
                    ('destination', '=', destination),
                ],
                limit=1,
            )
        )
        if not operation or not reference:
            raise UserError(
                _('Provider acceptance is not recorded yet. Retry this status later.')
            )
        operation.lock_for_update()
        self._apply_status(
            account,
            operation,
            status,
            reference,
            'rejected' if status == 'failed' else 'none',
        )
        return True
