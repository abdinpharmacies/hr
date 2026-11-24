import hashlib
import json
import re
from copy import deepcopy
from urllib.parse import urlsplit
from uuid import UUID

from lxml import html
from odoo.tools import html2plaintext

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError, LockError, ConcurrencyError
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from odoo.addons.ab_crm_sales_workspace.models.workspace import (
    normalized_phone,
    _WORKSPACE,
)
from ..protocol import validate, validate_chat, validate_lifecycle


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    provider = fields.Selection(
        selection_add=[('website', 'Website')],
        ondelete={'website': lambda records: records._prevent_provider_removal()},
    )

    def _valid_incoming_identity(self, value):
        if self.provider != 'website':
            return super()._valid_incoming_identity(value)
        try:
            return str(UUID(value)) == value
        except (ValueError, TypeError, AttributeError):
            return False

    def _queue_eligibility(self, conversation):
        code, reason = super()._queue_eligibility(conversation)
        if not code and self.provider == 'website':
            available = self.env['ab_crm_message'].search_count([
                ('conversation_id.channel_id', '=', self.channel_id.id),
                ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
                ('direction', '=', 'in'), '|', ('website_chat_event_id', '!=', False), ('website_order_id.chat_ready', '=', True),
                '|', ('conversation_id', '=', (conversation.website_canonical_id or conversation).id),
                ('conversation_id.website_canonical_id', '=', (conversation.website_canonical_id or conversation).id),
            ], limit=1)
            if not self.outgoing_enabled or not available:
                return 'outgoing_disabled', _('Website replies are disabled.')
        return code, reason


class WebsiteCustomer(models.Model):
    _name = 'ab_crm_website_customer'
    _inherit = 'ab_crm_scoped'
    _description = 'Website Customer Identity'

    account_id = fields.Many2one('ab_crm_messaging_account', required=True, ondelete='restrict')
    identity_key = fields.Char(required=True, index=True)
    conversation_id = fields.Many2one('ab_crm_conversation', required=True, ondelete='restrict')
    latest_order_id = fields.Many2one('ab_crm_website_order', ondelete='restrict')
    _unique_identity = models.Constraint(
        'UNIQUE(account_id, branch_id, company_id, identity_key)',
        'Website customer identity already exists.',
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    @api.constrains('account_id', 'conversation_id', 'latest_order_id', 'branch_id', 'company_id')
    def _check_identity_scope(self):
        for record in self:
            account, conversation = record.account_id, record.conversation_id
            if (account.provider != 'website' or conversation.channel_id != account.channel_id
                    or any(target.branch_id != record.branch_id or target.company_id != record.company_id
                           for target in (account, conversation))
                    or (record.latest_order_id and (
                        record.latest_order_id.account_id != account
                        or record.latest_order_id.conversation_id != conversation))):
                raise ValidationError(_('Invalid website order.'))


class WebsiteOrder(models.Model):
    _name = 'ab_crm_website_order'
    _inherit = 'ab_crm_scoped'
    _description = 'Website Order'
    _rec_name = 'reference'

    account_id = fields.Many2one(
        'ab_crm_messaging_account', required=True, ondelete='restrict'
    )
    order_uuid = fields.Char(required=True, index=True)
    reference = fields.Char(required=True)
    public_reference = fields.Char(string='Order Reference', readonly=True)
    account_identity = fields.Char(readonly=True, index=True)
    chat_ready = fields.Boolean(readonly=True)
    chat_closed = fields.Boolean(string='Order chat ended', readonly=True)
    phone = fields.Char(index=True)
    conversation_id = fields.Many2one(
        'ab_crm_conversation', required=True, ondelete='restrict'
    )
    website_customer_id = fields.Many2one('ab_crm_website_customer', ondelete='restrict', index=True)
    revision = fields.Integer(required=True)
    snapshot = fields.Json(required=True)
    payment_method_codes = fields.Json(default=dict, readonly=True)
    handoff_id = fields.Many2one('ab_crm_pos_handoff', ondelete='restrict')
    progress = fields.Selection(
        [('new', 'New'), ('review', 'Review'), ('prepared', 'Prepared')],
        default='new',
        required=True,
    )
    _unique_order = models.Constraint(
        'UNIQUE(account_id, order_uuid)', 'Website order already exists.'
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    @api.model
    def website_reconciliation_preview(self, account_id, limit=500):
        raise AccessError(_('Chat linking is disabled.'))

    @api.model
    def website_reconciliation_apply(self, account_id, fingerprint, limit=500):
        raise AccessError(_('Chat linking is disabled.'))

    def _website_reconciliation_apply(self, account_id, fingerprint, limit):
        raise AccessError(_('Chat linking is disabled.'))

    def _display_delivery_address(self, address):
        lines = [' '.join(line.split()) for line in address.splitlines() if line.strip()]
        fallback = ' '.join(lines)
        country = self.env.ref('base.eg')
        languages = self.env['res.lang'].search(fields.Domain('active', '=', True) & fields.Domain('code', 'in', ('en_US', 'ar_001'))).mapped('code')
        country_names = {country.with_context(lang=language).name for language in languages}
        if len(lines) < 2 or lines[-1] not in country_names:
            return fallback
        for state in country.state_ids:
            match = re.fullmatch(
                rf'(?:(?P<city>.*?)\s+)?{re.escape(state.code)}'
                rf'(?:\s+(?P<zip>\d{{3,10}}))?',
                lines[-2],
            )
            if match:
                details = ' '.join(filter(None, [
                    *lines[:-2], match.group('city'), match.group('zip'),
                ]))
                return ' | '.join(filter(None, [state.name, details]))
        return fallback

    def _display_snapshot(self, snapshot):
        self.ensure_one()
        self._authorize('read')
        result = deepcopy(snapshot)
        result['public_reference'] = snapshot.get('public_reference') or self.public_reference or ''
        result['display_delivery_address'] = self._display_delivery_address(
            result['customer']['address']
        )
        note = result.get('notes') or ''
        if note:
            try:
                root = html.fragment_fromstring(note, create_parent='div')
                for paragraph in root.xpath('.//p'):
                    if any(
                        urlsplit(link.get('href', '')).path.rstrip('/') == '/terms'
                        for link in paragraph.xpath('.//a[@href]')
                    ):
                        paragraph.drop_tree()
                note = html2plaintext(html.tostring(root, encoding='unicode')).strip()
            except (ValueError, html.etree.ParserError):
                note = html2plaintext(note).strip()
        result['display_notes'] = note
        labels = {
            'cash_on_delivery': _('Cash on delivery'),
            'wire_transfer': _('Bank transfer'),
            'card': _('Card'),
        }
        methods = []
        for payment in result.get('payments', []):
            code = payment.get('method') or (self.payment_method_codes or {}).get(
                payment.get('reference')
            )
            label = labels.get(code) or (
                _('Online payment') if payment.get('provider') not in ('custom', '', None)
                else _('Not specified')
            )
            if label not in methods:
                methods.append(label)
        result['payment_method_label'] = ' / '.join(methods) or _('Not specified')
        return result


class WebsiteEvent(models.Model):
    _name = 'ab_crm_website_event'
    _inherit = 'ab_crm_scoped'
    _description = 'Website Event'

    account_id = fields.Many2one(
        'ab_crm_messaging_account', required=True, ondelete='restrict'
    )
    event_uuid = fields.Char(required=True)
    order_uuid = fields.Char(required=True)
    revision = fields.Integer(required=True)
    fingerprint = fields.Char(required=True)
    envelope = fields.Json(required=True)
    _unique_event = models.Constraint(
        'UNIQUE(account_id, event_uuid)', 'Website event already exists.'
    )
    _unique_revision = models.Constraint(
        'UNIQUE(account_id, order_uuid, revision)', 'Website revision already exists.'
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Website evidence is immutable.'))


class Mapping(models.Model):
    _name = 'ab_crm_website_mapping'
    _inherit = 'ab_crm_scoped'
    _description = 'Website Unit Mapping'

    account_id = fields.Many2one(
        'ab_crm_messaging_account', required=True, ondelete='restrict'
    )
    serial = fields.Char(required=True)
    unit_code = fields.Char(required=True)
    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_product_uom', required=True, ondelete='restrict')
    active = fields.Boolean(default=True)
    _unique_mapping = models.Constraint(
        'UNIQUE(account_id, serial, unit_code)', 'Website mapping already exists.'
    )

    @api.constrains(
        'account_id', 'serial', 'product_id', 'uom_id', 'branch_id', 'company_id'
    )
    def _check_mapping(self):
        for record in self:
            record.account_id.check_access('read')
            record.product_id.check_access('read')
            record.uom_id.check_access('read')
            if (
                record.account_id.provider != 'website'
                or record.account_id.branch_id != record.branch_id
                or record.account_id.company_id != record.company_id
                or not record.product_id.active
                or str(record.product_id.eplus_serial) != record.serial
                or not record.product_id.eplus_serial
                or not record.product_id.allow_sale
                or not record.uom_id.active
                or record.uom_id.factor <= 0
                or not record.product_id.uom_category_id
                or record.uom_id.category_id != record.product_id.uom_category_id
                or (
                    record.product_id.only_default_sales_uom
                    and record.uom_id != record.product_id.uom_id
                )
            ):
                raise ValidationError(_('Invalid website product or scope mapping.'))


class Gateway(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    @api.model
    def website_capabilities(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider != 'website' or not account.enabled:
            raise AccessError(_('Website intake is disabled.'))
        return {'version': 4}

    @api.model
    def receive_website_lifecycle(self, account_code, provider_account, event):
        account = self._account(account_code, provider_account)
        if account.provider != 'website' or not account.enabled or not account.active or not account.channel_id.sudo().active:
            raise AccessError(_('Website intake is disabled.'))
        try:
            validate_lifecycle(event)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValidationError(_('Invalid website event.')) from None
        if event['source'] != provider_account:
            raise AccessError(_('Invalid website source.'))
        account.branch_id.lock_for_update()
        ledger = self.env['ab_crm_website_chat_event'].sudo()
        existing = ledger.search([('account_id', '=', account.id), ('event_uuid', '=', event['event_uuid'])], limit=1)
        if existing:
            if existing.fingerprint != event['fingerprint']:
                raise ValidationError(_('Conflicting website event.'))
            return {'received': True, 'event_uuid': event['event_uuid']}
        if event['destination']['kind'] == 'order':
            order = self.env['ab_crm_website_order'].sudo().search([
                ('account_id', '=', account.id), ('order_uuid', '=', event['destination']['uuid']),
            ], limit=1)
            if (not order or order.branch_id != account.branch_id or order.company_id != account.company_id
                    or (event['kind'] == 'identity_bound' and order.account_identity and order.account_identity != event['identity']['uuid'])):
                raise AccessError(_('Invalid website source.'))
            mutation = _MUTATION.set(True)
            try:
                if event['kind'] == 'order_dispatched':
                    if not order.chat_closed:
                        order.write({'chat_closed': True})
                elif not order.chat_closed:
                    identity_uuid = event['identity']['uuid']
                    siblings = self.env['ab_crm_website_order'].sudo().search([
                        ('account_id', '=', account.id), ('conversation_id', '=', order.conversation_id.id),
                        ('id', '!=', order.id),
                    ])
                    if any(sibling.account_identity != identity_uuid and not (
                            order.visitor_identity and sibling.visitor_identity == order.visitor_identity)
                           for sibling in siblings):
                        raise AccessError(_('Invalid website source.'))
                    order.write({'account_identity': identity_uuid})
                    identities = self.env['ab_crm_website_customer'].sudo()
                    identity = identities.search([('account_id', '=', account.id), ('identity_key', '=', 'account:' + identity_uuid)], limit=1)
                    canonical = identity.conversation_id if identity else order.conversation_id
                    internal = _INTERNAL.set(True)
                    try:
                        canonical.write({'website_account_identity': identity_uuid})
                        if canonical != order.conversation_id:
                            order.conversation_id.write({'website_canonical_id': canonical.id,
                                'website_account_identity': identity_uuid})
                        if not identity:
                            identities.create({'account_id': account.id, 'identity_key': 'account:' + identity_uuid,
                                'conversation_id': canonical.id, 'branch_id': account.branch_id.id, 'company_id': account.company_id.id})
                    finally:
                        _INTERNAL.reset(internal)
                ledger.create({'account_id': account.id, 'event_uuid': event['event_uuid'],
                    'fingerprint': event['fingerprint'], 'envelope': event,
                    'branch_id': account.branch_id.id, 'company_id': account.company_id.id})
            finally:
                _MUTATION.reset(mutation)
            return {'received': True, 'event_uuid': event['event_uuid']}
        session = self.env['ab_crm_website_session'].sudo().search([
            ('account_id', '=', account.id), ('session_uuid', '=', event['destination']['uuid']),
        ], limit=1)
        if not session:
            raise ValidationError(_('Invalid website order.'))
        mutation, internal = _MUTATION.set(True), _INTERNAL.set(True)
        try:
            identity_uuid = event['identity']['uuid']
            if event['kind'] == 'session_ended':
                if identity_uuid not in (session.identity_uuid, session.account_identity):
                    raise AccessError(_('Invalid website source.'))
                if not session.ended:
                    session.write({'ended': True})
                canonical = session.conversation_id.website_canonical_id or session.conversation_id
                if session.identity_kind == 'visitor' and not session.account_identity:
                    active_sessions = self.env['ab_crm_website_session'].sudo().search_count([
                        ('account_id', '=', account.id), ('branch_id', '=', account.branch_id.id),
                        ('company_id', '=', account.company_id.id), ('ended', '=', False),
                        '|', ('conversation_id', '=', canonical.id), ('conversation_id.website_canonical_id', '=', canonical.id),
                    ], limit=1)
                    if not active_sessions and not canonical.website_account_identity:
                        canonical.write({'state': 'closed'})
            else:
                if session.ended or (session.account_identity and session.account_identity != identity_uuid):
                    raise AccessError(_('Invalid website source.'))
                identities = self.env['ab_crm_website_customer'].sudo()
                identity = identities.search([('account_id', '=', account.id),
                    ('identity_key', '=', 'account:' + identity_uuid)], limit=1)
                canonical = identity.conversation_id if identity else session.conversation_id
                if session.conversation_id.website_account_identity and session.conversation_id.website_account_identity != identity_uuid:
                    raise AccessError(_('Invalid website source.'))
                canonical_values = {'website_account_identity': identity_uuid}
                if 'phone' in event['identity']:
                    canonical_values['website_phone'] = event['identity']['phone']
                if event['identity'].get('name'):
                    canonical_values['name'] = event['identity']['name'].strip()
                    canonical_values['website_customer_name'] = event['identity']['name'].strip()
                canonical.write(canonical_values)
                if not identity:
                    identities.create({'account_id': account.id, 'identity_key': 'account:' + identity_uuid,
                        'conversation_id': canonical.id, 'branch_id': account.branch_id.id, 'company_id': account.company_id.id})
                if canonical != session.conversation_id:
                    session.conversation_id.write({'website_canonical_id': canonical.id,
                                                   'website_account_identity': identity_uuid})
                session.write({'account_identity': identity_uuid})
            ledger.create({'account_id': account.id, 'event_uuid': event['event_uuid'],
                'fingerprint': event['fingerprint'], 'envelope': event,
                'branch_id': account.branch_id.id, 'company_id': account.company_id.id})
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        return {'received': True, 'event_uuid': event['event_uuid']}

    def _website_operation_allowed(self, account, operation):
        if not account.outgoing_enabled:
            return False
        try:
            operation.message_id._website_destination(account)
            return operation.content == operation.message_id._outgoing_extra() and (
                operation.destination == operation.message_id.conversation_id.external_key
            )
        except (AccessError, UserError, ValidationError):
            return False

    @api.model
    def lease_outgoing(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider != 'website':
            return super().lease_outgoing(account_code, provider_account)
        if not account.outgoing_enabled:
            return False
        operations = self.env['ab_crm_messaging_operation'].sudo().search([
            ('account_id', '=', account.id), ('state', 'in', ['queued', 'leased']),
        ], order='id', limit=100)
        for operation in operations:
            if not self._website_operation_allowed(account, operation):
                operation._change({'state': 'review',
                    'error_code': 'rejected' if (operation.message_id.website_session_id.ended or operation.message_id.website_order_id.chat_closed) else 'ambiguous',
                    'review_note': operation.message_id._website_closed_reason() or False})
        result = super().lease_outgoing(account_code, provider_account)
        if result:
            operation = self._operation(account, result['token'], result['attempt'])
            if not self._website_operation_allowed(account, operation):
                operation._change({'state': 'review',
                    'error_code': 'rejected' if (operation.message_id.website_session_id.ended or operation.message_id.website_order_id.chat_closed) else 'ambiguous',
                    'review_note': operation.message_id._website_closed_reason() or False})
                return False
        return result

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        account = self._account(account_code, provider_account)
        if account.provider == 'website':
            operation = self._operation(account, token, attempt)
            if (operation.message_id.website_session_id.ended or operation.message_id.website_order_id.chat_closed):
                operation._change({'review_note': operation.message_id._website_closed_reason()})
                return {'allowed': False, 'terminal': True, 'error': 'rejected'}
            if not self._website_operation_allowed(account, operation):
                return False
        return super().authorize_send(account_code, provider_account, token, attempt, receipt)

    @api.model
    def receive_website_chat(self, account_code, provider_account, event):
        account = self._account(account_code, provider_account)
        if (account.provider != 'website' or not account.enabled or not account.active
                or not account.channel_id.sudo().active or not self.env.user.active):
            raise AccessError(_('Website intake is disabled.'))
        try:
            validate_chat(event)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValidationError(_('Invalid website event.')) from None
        if event['source'] != provider_account:
            raise AccessError(_('Invalid website source.'))
        account.branch_id.lock_for_update()
        account.branch_id.sudo().write({})
        scope = {'branch_id': account.branch_id.id, 'company_id': account.company_id.id}
        ledger = self.env['ab_crm_website_chat_event'].sudo().with_context(
            allowed_company_ids=account.company_id.ids)
        existing = ledger.search([('account_id', '=', account.id),
                                  ('event_uuid', '=', event['event_uuid'])], limit=1)
        if existing:
            if existing.fingerprint != event['fingerprint']:
                raise ValidationError(_('Conflicting website event.'))
            return {'received': True, 'event_uuid': event['event_uuid']}
        destination = event['destination']
        order = self.env['ab_crm_website_order'].sudo().search([
            ('account_id', '=', account.id), ('order_uuid', '=', destination['uuid']),
            ('branch_id', '=', account.branch_id.id), ('company_id', '=', account.company_id.id),
        ], limit=1) if destination['kind'] == 'order' else False
        if destination['kind'] == 'order' and not order:
            raise AccessError(_('Invalid website order.'))
        if (order and order.account_identity and event['identity']['kind'] == 'customer'
                and event['identity']['uuid'] != order.account_identity):
            raise AccessError(_('Invalid website source.'))
        if order and order.chat_closed:
            raise ValidationError(_('This chat has ended. Your order has been sent for delivery.'))
        sessions = self.env['ab_crm_website_session'].sudo().with_context(
            allowed_company_ids=account.company_id.ids)
        session = sessions.search([('account_id', '=', account.id),
                                  ('session_uuid', '=', destination['uuid'])], limit=1)
        if destination['kind'] == 'livechat' and session and session.ended:
            raise ValidationError(_('This website chat has ended.'))
        if destination['kind'] == 'livechat' and session and (
                event['identity']['uuid'] not in (session.identity_uuid, session.account_identity)
                or (not session.account_identity and session.identity_kind != event['identity']['kind'])):
            raise AccessError(_('Invalid website source.'))
        mutation, internal = _MUTATION.set(True), _INTERNAL.set(True)
        try:
            verified = (order.account_identity if order else event['identity']['uuid']) if event['identity']['kind'] == 'customer' else False
            identities = self.env['ab_crm_website_customer'].sudo().with_context(allowed_company_ids=account.company_id.ids)
            identity = identities.search([('account_id', '=', account.id),
                ('identity_key', '=', 'account:' + verified if verified else 'visitor:' + event['identity']['uuid'])], limit=1)
            sender = identity.conversation_id.external_key if identity else (verified or (
                order.conversation_id.external_key if order else (
                    (session.conversation_id.website_canonical_id or session.conversation_id).external_key
                    if session else event['identity']['uuid'])))
            received = super().receive_event(account_code, provider_account, {
                'id': event['event_uuid'], 'sender': sender, 'body': event['body'] or _('Attachment'),
                'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
                'unsupported': False, 'source_digest': event['fingerprint'],
            })
            message = self.env['ab_crm_message'].sudo().browse(received['message_id'])
            if not verified and not identity and not order:
                identities.create(dict(scope, account_id=account.id, identity_key='visitor:' + event['identity']['uuid'],
                    conversation_id=message.conversation_id.id))
            if verified and not identity:
                identities.create(dict(scope, account_id=account.id, identity_key='account:' + verified,
                    conversation_id=message.conversation_id.id))
                message.conversation_id.write({'website_account_identity': verified})
            if verified:
                values = {}
                if event['identity'].get('name'):
                    values['name'] = event['identity']['name'].strip()
                    values['website_customer_name'] = event['identity']['name'].strip()
                if 'phone' in event['identity']:
                    values['website_phone'] = event['identity']['phone']
                if values:
                    message.conversation_id.write(values)
            if order:
                if verified and order.account_identity and order.account_identity != verified:
                    raise AccessError(_('Invalid website source.'))
                order.write(dict(chat_ready=True, **({'account_identity': verified} if verified else {})))
                message.write({'website_order_id': order.id})
            else:
                if not session:
                    session = sessions.create(dict(scope, account_id=account.id,
                        session_uuid=destination['uuid'], identity_uuid=event['identity']['uuid'],
                        identity_kind=event['identity']['kind'], conversation_id=message.conversation_id.id,
                        account_identity=verified))
                message.write({'website_session_id': session.id})
                name = _('Visitor')
                if session.identity_kind == 'customer' or session.account_identity:
                    name = event['identity'].get('name')
                    if name:
                        name = name.strip()
                    else:
                        name = message.conversation_id.name if message.conversation_id.name != message.conversation_id.external_key else _('Customer')
                values = {'name': name}
                if event['identity']['kind'] == 'customer' and 'phone' in event['identity']:
                    values['website_phone'] = event['identity']['phone']
                if message.conversation_id.state == 'closed':
                    values.update(state='new', assigned_id=False)
                message.conversation_id.write(values)
            chat_event = ledger.create(dict(scope, account_id=account.id, event_uuid=event['event_uuid'],
                               fingerprint=event['fingerprint'], envelope=event))
            message.write({'website_chat_event_id': chat_event.id})
            if event.get('attachments'):
                self._website_link_media(account, event, message)
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        return {'received': True, 'event_uuid': event['event_uuid']}

    @api.model
    def receive_website_event(self, account_code, provider_account, event):
        try:
            account = self._account(account_code, provider_account)
        except LockError:
            raise ConcurrencyError('Website intake is busy') from None
        if (
            not self.env.user.active
            or account.provider != 'website'
            or not account.enabled
            or not account.active
            or not account.channel_id.sudo().active
        ):
            raise AccessError(_('Website intake is disabled.'))
        try:
            validate(event)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValidationError(_('Invalid website event.')) from None
        if event['source'] != provider_account:
            raise AccessError(_('Invalid website source.'))
        try:
            account.branch_id.lock_for_update()
        except LockError:
            raise ConcurrencyError('Website intake is busy') from None
        account.branch_id.sudo().write({})
        scope = {'branch_id': account.branch_id.id, 'company_id': account.company_id.id}
        context = {'allowed_company_ids': account.company_id.ids}
        ledger = self.env['ab_crm_website_event'].sudo().with_context(context)
        existing = ledger.search(
            [('account_id', '=', account.id), ('event_uuid', '=', event['event_uuid'])],
            limit=1,
        )
        if existing:
            if existing.fingerprint != event['fingerprint']:
                raise ValidationError(_('Conflicting website event.'))
            return {'received': True, 'event_uuid': event['event_uuid']}
        orders = self.env['ab_crm_website_order'].sudo().with_context(context)
        order = orders.search(
            [('account_id', '=', account.id), ('order_uuid', '=', event['order_uuid'])],
            limit=1,
        )
        if event['revision'] != (order.revision + 1 if order else 1) or (
            not order and event['kind'] != 'order'
        ):
            raise ValidationError(_('Website revisions must arrive in order.'))
        if order and order.chat_closed and event['kind'] == 'message':
            raise ValidationError(_('This chat has ended. Your order has been sent for delivery.'))
        mutation = _MUTATION.set(True)
        try:
            payload = event['payload']
            body = (
                payload['body']
                if event['kind'] == 'message'
                else _('Website Order: %s') % payload['reference']
            )
            phone = normalized_phone(
                payload['customer']['phone'], account.company_id.country_id.code
            ) if not order else order.phone
            identities = self.env['ab_crm_website_customer'].sudo().with_context(context)
            verified = payload.get('account_identity') if event['kind'] == 'order' and not order else False
            visitor = payload.get('visitor_identity') if event['kind'] == 'order' and not order else False
            identity_key = 'account:' + verified if verified else ('visitor:' + visitor if visitor else 'order:' + event['order_uuid'])
            identity = order.website_customer_id if order and order.website_customer_id else identities.search([
                ('account_id', '=', account.id), ('branch_id', '=', account.branch_id.id),
                ('company_id', '=', account.company_id.id), ('identity_key', '=', identity_key),
            ], limit=1)
            sender = identity.conversation_id.external_key if identity else (
                order.conversation_id.external_key if order else event['order_uuid'])
            received = super().receive_event(
                account_code,
                provider_account,
                {
                    'id': event['event_uuid'],
                    'sender': sender,
                    'body': body,
                    'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
                    'unsupported': False,
                    'source_digest': event['fingerprint'],
                },
            )
            if not order:
                conversation = (
                    self.env['ab_crm_conversation']
                    .sudo()
                    .search(
                        [
                            ('channel_id', '=', account.channel_id.id),
                            ('external_key', '=', sender),
                        ],
                        limit=1,
                    )
                )
                order = orders.create(
                    dict(
                        scope,
                        account_id=account.id,
                        order_uuid=event['order_uuid'],
                        reference=payload['reference'],
                        public_reference=payload.get('public_reference') or False,
                        account_identity=verified,
                        origin_kind=payload.get('origin_kind') or False,
                        visitor_identity=payload.get('visitor_identity') or False,
                        phone=phone,
                        conversation_id=conversation.id,
                        revision=event['revision'],
                        snapshot=payload,
                    )
                )
                conversation.write(
                    {
                        'name': '%s · %s'
                        % (payload['customer']['name'], phone or payload['customer']['phone']),
                        'website_phone': phone,
                        'website_account_identity': verified,
                    }
                )
            else:
                values = {'revision': event['revision']}
                if event['kind'] == 'order':
                    values.update(snapshot=payload, progress='review')
                    if payload.get('public_reference'):
                        values['public_reference'] = payload['public_reference']
                order.write(values)
            if not identity:
                identity = identities.create(dict(
                    scope, account_id=account.id, identity_key=identity_key,
                    conversation_id=order.conversation_id.id,
                ))
            if not order.website_customer_id:
                order.write({'website_customer_id': identity.id})
            identity.write({'latest_order_id': order.id})
            message = self.env['ab_crm_message'].sudo().browse(received['message_id'])
            internal = _INTERNAL.set(True)
            try:
                message.write({'website_order_id': order.id})
                order.write({'chat_ready': True})
            finally:
                _INTERNAL.reset(internal)
            ledger.create(
                dict(
                    scope,
                    account_id=account.id,
                    event_uuid=event['event_uuid'],
                    order_uuid=event['order_uuid'],
                    revision=event['revision'],
                    fingerprint=event['fingerprint'],
                    envelope=event,
                )
            )
        finally:
            _MUTATION.reset(mutation)
        return {'received': True, 'event_uuid': event['event_uuid']}


class Message(models.Model):
    _inherit = 'ab_crm_message'

    website_closure_notice = fields.Boolean(string='Chat closure notice', readonly=True)
    website_order_id = fields.Many2one('ab_crm_website_order', readonly=True, ondelete='restrict', index=True)
    website_session_id = fields.Many2one('ab_crm_website_session', readonly=True, ondelete='restrict', index=True)
    website_chat_event_id = fields.Many2one('ab_crm_website_chat_event', readonly=True, ondelete='restrict')

    @api.model_create_multi
    def create(self, values_list):
        if any({'website_order_id', 'website_session_id', 'website_chat_event_id', 'website_closure_notice'} & values.keys() for values in values_list) and not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if {'website_order_id', 'website_session_id', 'website_chat_event_id', 'website_closure_notice'} & values.keys() and not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def _website_closed_reason(self):
        self.ensure_one()
        if self.website_order_id.chat_closed:
            return _('This chat has ended. Your order has been sent for delivery.')
        if self.website_session_id.ended:
            return _('The guest has left the conversation.') if self.website_session_id.identity_kind == 'visitor' and not self.website_session_id.account_identity else _('This website chat has ended.')
        return False

    def _website_destination(self, account):
        self.ensure_one()
        conversation = self.conversation_id
        target = self.website_order_id or self.website_session_id
        if (not target or bool(self.website_order_id) == bool(self.website_session_id)
                or target.account_id != account
                or ((target.conversation_id.website_canonical_id or target.conversation_id) != (conversation.website_canonical_id or conversation)
                    and not (self.website_order_id and target.account_identity
                             and target.account_identity == conversation.website_account_identity))
                or target.branch_id != conversation.branch_id or target.company_id != conversation.company_id
                or conversation.channel_id != account.channel_id or conversation.branch_id != account.branch_id
                or conversation.company_id != account.company_id
                or (self.website_order_id and not self.website_order_id.chat_ready)):
            raise AccessError(_('Invalid website order.'))
        target.lock_for_update()
        target.invalidate_recordset()
        reason = self._website_closed_reason()
        if reason:
            raise UserError(reason)
        return {'kind': 'order' if self.website_order_id else 'livechat',
                'uuid': target.order_uuid if self.website_order_id else target.session_uuid}

    def _outgoing_extra(self):
        result = super()._outgoing_extra()
        if self.conversation_id.channel_id.provider == 'website':
            if any(value for key, value in result.items() if key != 'media') or self.reply_reference or self.reaction:
                raise ValidationError(_('Invalid website reply.'))
            result['website_destination'] = self._website_destination(self.conversation_id.messaging_account_id)
            from .media import upload_descriptor
            result['media'] = [dict(upload_descriptor(item), id=str(media.id))
                for media, item in zip(self.media_ids, result.get('media', []))]
        return result

    def action_approve(self):
        website = self.filtered(lambda m: m.conversation_id.channel_id.provider == 'website')
        website._staff_action()
        website._authorize()
        website.lock_for_update()
        for message in website:
            message.conversation_id._owned()
            account = message.conversation_id.messaging_account_id
            account._authorize('read')
            account.lock_for_update()
            account._eligible_message(message)
            message._website_destination(account)
        result = super().action_approve()
        mutation = _MUTATION.set(True)
        try:
            for message in website:
                account = message.conversation_id.messaging_account_id
                self.env['ab_crm_messaging_operation'].sudo().with_context(
                    allowed_company_ids=message.company_id.ids).create({
                    'account_id': account.id, 'message_id': message.id, 'body': message.body,
                    'content': message._outgoing_extra(), 'destination': message.conversation_id.external_key,
                    'branch_id': message.branch_id.id, 'company_id': message.company_id.id,
                    'approved_by': self.env.uid, 'approved_at': message.approved_at,
                })
                message._internal_write({'delivery_state': 'unknown'})
        finally:
            _MUTATION.reset(mutation)
        return result


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    website_account_identity = fields.Char(readonly=True, index=True, copy=False)
    website_phone = fields.Char(readonly=True, index=True, copy=False)
    website_customer_name = fields.Char(string='Verified customer name', readonly=True, copy=False)
    website_canonical_id = fields.Many2one('ab_crm_conversation', readonly=True, ondelete='restrict', index=True)


    @api.depends(
        'customer_id', 'branch_id', 'company_id', 'website_phone', 'channel_id.provider',
        'external_key', 'channel_id', 'website_canonical_id', 'website_account_identity'
    )
    def _compute_customer_group_key(self):
        super()._compute_customer_group_key()
        for record in self:
            if record.channel_id.provider == 'website':
                record.customer_group_key = (
                    f'{record.company_id.id}:{record.branch_id.id}:{record.channel_id.id}:website-account:{record.website_account_identity}'
                    if record.website_account_identity else (
                    f'{record.company_id.id}:{record.branch_id.id}:{record.channel_id.id}:website-order:{record.external_key or record.id}'
                ))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
            if ({'website_phone', 'website_customer_name', 'website_canonical_id', 'website_account_identity'} & values.keys() and not _MUTATION.get()) or (
                channel.provider == 'website'
                and values.get('customer_id')
                and not _WORKSPACE.get()
            ):
                raise AccessError(_('Use reviewed website customer linking.'))
        return super().create(values_list)

    def write(self, values):
        if ({'website_phone', 'website_customer_name', 'website_canonical_id', 'website_account_identity'} & values.keys() and not _MUTATION.get()) or (
            'customer_id' in values
            and not _WORKSPACE.get()
            and any(r.channel_id.provider == 'website' for r in self)
        ):
            raise AccessError(_('Use reviewed website customer linking.'))
        return super().write(values)

    def action_customer_link_candidates(self):
        raise AccessError(_('Chat linking is disabled.'))

    def _customer_link_preview(self, customer, account):
        identity, preview = super()._customer_link_preview(customer, account)
        if self.channel_id.provider == 'website':
            preview.update(automatic_match=False)
        return identity, preview

    def _workspace_inbox_domain(self, query):
        domain = super()._workspace_inbox_domain(query) + [('website_canonical_id', '=', False)]
        session = self._workspace_actor()
        phone = (
            normalized_phone(query, session.company_id.country_id.code)
            if query
            else False
        )
        if phone:
            scope = fields.Domain(super()._workspace_inbox_domain('') + [('website_canonical_id', '=', False)])
            return list(
                fields.Domain(domain)
                | (scope & fields.Domain('website_phone', '=', phone))
            )
        return domain

    def _website_timeline_streams(self):
        self.ensure_one()
        self._workspace_scope()
        canonical = self.website_canonical_id or self
        candidates = self.with_context(active_test=False).search([
            ('company_id', '=', self.company_id.id), ('branch_id', '=', self.branch_id.id),
            ('channel_id', '=', self.channel_id.id),
            '|', ('id', '=', canonical.id), ('website_canonical_id', '=', canonical.id),
        ])
        for conversation in candidates:
            conversation._workspace_scope()
        return candidates

    def _workspace_streams(self):
        if self.channel_id.provider == 'website':
            self._workspace_scope()
            return self.website_canonical_id or self
        return super()._workspace_streams()

    def _workspace_inbox_rows(self, session):
        rows = super()._workspace_inbox_rows(session)
        for row in rows:
            conversation = self.browse(row['id'])
            if conversation.channel_id.provider != 'website' or conversation.website_canonical_id:
                continue
            aliases = conversation._website_timeline_streams() - conversation
            if aliases:
                alias_rows = super(Conversation, aliases)._workspace_inbox_rows(session)
                row['unread'] += sum(alias['unread'] for alias in alias_rows)
        return rows

    def _customer_unlink_streams(self):
        streams = super()._customer_unlink_streams()
        aliases = self.with_context(active_test=False).search([
            ('customer_id', '=', self.customer_id.id),
            ('company_id', '=', self.company_id.id), ('branch_id', '=', self.branch_id.id),
            ('channel_id.active', '=', True), ('website_canonical_id', '!=', False),
        ])
        for stream in aliases:
            stream._workspace_scope()
        return streams | aliases

    def _customer_link_group(self):
        if self.channel_id.provider == 'website':
            return self._website_timeline_streams()
        return super()._customer_link_group()

    def workspace_channel(self, conversation_id):
        if self.channel_id.provider == 'website' and not self.customer_id:
            self._workspace_scope()
            if type(conversation_id) is not int:
                raise AccessError(_('Invalid website order.'))
            destination = self._website_timeline_streams().filtered(lambda record: record.id == conversation_id)
            if not destination:
                raise AccessError(_('Invalid website order.'))
            return destination.workspace_detail()
        return super().workspace_channel(conversation_id)

    def _recompute_website_customer_groups(self, limit=500, after_id=0):
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Use reviewed website customer linking.'))
        if type(limit) is not int or not 1 <= limit <= 500 or type(after_id) is not int or after_id < 0:
            raise ValidationError(_('Invalid website order.'))
        records = self.with_context(active_test=False).search([('channel_id.provider', '=', 'website'), ('id', '>', after_id)],
                              order='id', limit=limit)
        records._authorize()
        self.env.add_to_compute(records._fields['customer_group_key'], records)
        records._recompute_recordset(['customer_group_key'])
        return records.ids

    def workspace_acknowledge(self, message_id):
        if self.channel_id.provider != 'website':
            return super().workspace_acknowledge(message_id)
        streams = self._website_timeline_streams()
        if type(message_id) is not int:
            raise AccessError(_('Invalid read position.'))
        message = self.env['ab_crm_message'].search([
            ('id', '=', message_id), ('conversation_id', 'in', streams.ids),
        ], limit=1)
        if not message:
            raise AccessError(_('Invalid read position.'))
        for stream in streams.sorted('id'):
            latest = self.env['ab_crm_message'].search([
                ('conversation_id', '=', stream.id), ('id', '<=', message_id),
            ], order='id desc', limit=1)
            if latest:
                super(Conversation, stream).workspace_acknowledge(latest.id)
        return True

    def workspace_focus(self, message_id):
        if self.channel_id.provider != 'website':
            return super().workspace_focus(message_id)
        self._workspace_scope()
        message = self.env['ab_crm_message'].search([
            ('id', '=', message_id), ('conversation_id', 'in', self._website_timeline_streams().ids),
            ('direction', '=', 'in'),
        ], limit=1)
        if not message:
            raise AccessError(_('Select a message from this conversation.'))
        result = self.workspace_detail(through_id=message.id)
        result['focus_message_id'] = message.id
        return result

    def _customer_display_name(self):
        if self.channel_id.provider == 'website' and not self.customer_id:
            return self._provider_display_name() or super()._customer_display_name()
        return super()._customer_display_name()

    def _display_destination(self):
        if self.channel_id.provider == 'website':
            return self._provider_display_name()
        return super()._display_destination()

    def _provider_display_name(self):
        if self.channel_id.provider == 'website':
            if self.website_account_identity and self.website_customer_name:
                return ' · '.join(filter(None, (self.website_customer_name, self.website_phone)))
            order = self.env['ab_crm_website_order'].search(
                [('conversation_id', '=', self.id)], limit=1
            )
            if order:
                return ' · '.join(filter(None, (order.snapshot['customer']['name'],
                    order.phone or order.snapshot['customer']['phone'])))
            session = self.env['ab_crm_website_session'].search([
                ('conversation_id', '=', self.id), ('account_id', '=', self.messaging_account_id.id),
            ], limit=1)
            if session:
                return (' · '.join(filter(None, (self.name, self.website_phone)))) if session.identity_kind == 'customer' or session.account_identity else _('Visitor')
        return super()._provider_display_name()

    def action_identify(self, phone=False, customer_id=False, confirmed=False):
        if self.channel_id.provider == 'website' and not phone:
            self._owned()
            order = self.env['ab_crm_website_order'].search(
                [('conversation_id', '=', self.id)], limit=1
            )
            phone = order.phone
        return super().action_identify(phone, customer_id, confirmed)

    def _website_reply_target(self, website_order_id=False, website_session_id=False):
        self.ensure_one()
        if website_session_id:
            if type(website_session_id) is not int or website_order_id:
                raise AccessError(_('Invalid website order.'))
            session = self.env['ab_crm_website_session'].search([
                ('id', '=', website_session_id), ('conversation_id', 'in', self._website_timeline_streams().ids),
                ('account_id', '=', self.messaging_account_id.id),
                ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
            ], limit=1)
            if not session:
                raise AccessError(_('Invalid website order.'))
            session.lock_for_update()
            session.invalidate_recordset(['ended'])
            if session.ended:
                raise AccessError(_('The guest has left the conversation.') if session.identity_kind == 'visitor' and not session.account_identity else _('This website chat has ended.'))
            return False, session
        if website_order_id and type(website_order_id) is not int:
            raise AccessError(_('Invalid website order.'))
        if website_order_id:
            order = self.env['ab_crm_website_order'].search([
                ('id', '=', website_order_id),
                '|', ('conversation_id', '=', self.id), ('account_identity', '=', self.website_account_identity or '__unbound__'),
                ('account_id', '=', self.messaging_account_id.id), ('chat_ready', '=', True),
                ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
            ], limit=1)
            if not order:
                raise AccessError(_('Invalid website order.'))
            order.lock_for_update()
            order.invalidate_recordset(['chat_closed'])
            if order.chat_closed:
                raise UserError(_('This chat has ended. Your order has been sent for delivery.'))
            return order, False
        incoming = self.env['ab_crm_message'].search([
            ('conversation_id', 'in', self._website_timeline_streams().ids), ('direction', '=', 'in'),
            '|', ('website_order_id', '=', False), ('website_order_id.chat_closed', '=', False),
            '|', ('website_session_id', '=', False), ('website_session_id.ended', '=', False),
            '|', ('website_chat_event_id', '!=', False), ('website_order_id.chat_ready', '=', True),
            ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
        ], order='id desc', limit=1)
        if not incoming:
            closed_order = self.env['ab_crm_website_order'].search([('conversation_id', 'in', self._website_timeline_streams().ids), ('account_id', '=', self.messaging_account_id.id), ('chat_closed', '=', True)], limit=1)
            if closed_order:
                raise UserError(_('This chat has ended. Your order has been sent for delivery.'))
            ended = self.env['ab_crm_website_session'].search([('conversation_id', 'in', self._website_timeline_streams().ids), ('account_id', '=', self.messaging_account_id.id), ('ended', '=', True)], limit=1)
            if ended:
                raise UserError(_('The guest has left the conversation.') if ended.identity_kind == 'visitor' and not ended.account_identity else _('This website chat has ended.'))
            raise UserError(_('Website replies are disabled.'))
        if incoming.website_session_id.ended:
            raise UserError(_('This website chat has ended.'))
        return incoming.website_order_id, incoming.website_session_id

    def _reply_eligibility(self):
        if self.channel_id.provider != 'website':
            return super()._reply_eligibility()
        try:
            self._authorize()
            self._workspace_scope()
            account = self.messaging_account_id
            code, reason = account._queue_eligibility(self)
            if code:
                return code, reason
            self._website_reply_target()
        except (AccessError, UserError) as error:
            return 'outgoing_disabled', str(error)
        return False, False

    def website_action_reply(self, body, website_order_id=False, attachments=None, reply_id=False, website_session_id=False, submission_uuid=False):
        self.ensure_one()
        self._owned()
        if self.channel_id.provider != 'website':
            raise AccessError(_('Invalid website order.'))
        if not isinstance(body, str) or (not body.strip() and not attachments):
            raise ValidationError(_('Invalid website reply.'))
        attachments = attachments or []
        if not isinstance(attachments, list) or len(attachments) > 4:
            raise ValidationError(_('Invalid website media.'))
        attachments = [self._website_attachment_payload(item) for item in attachments]
        submission = self._website_submission(submission_uuid, body, attachments, reply_id, website_order_id, website_session_id)
        if submission and submission.get('result'):
            return submission['result']
        self.messaging_account_id._eligible(self, body.strip() or _('Attachment'))
        order, session = self._website_selected_target(reply_id, website_order_id, website_session_id)
        for attachment in attachments:
            self._website_validate_upload(attachment)
        with self.env.cr.savepoint():
            mutation, internal = _MUTATION.set(True), _INTERNAL.set(True)
            try:
                message = self.env['ab_crm_message'].create({
                    'conversation_id': self.id, 'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id, 'direction': 'out', 'body': body.strip() or _('Attachment'),
                    'website_order_id': order.id if order else False,
                    'website_session_id': session.id if session else False,
                })
                message._website_destination(self.messaging_account_id)
                for attachment in attachments:
                    self.env['ab_crm_message_media'].sudo().create({
                        'message_id': message.id, 'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                        **{key: attachment[key] for key in ('name', 'kind', 'mimetype', 'size', 'data')},
                        'duration': attachment.get('duration', 0), 'state': 'ready',
                    })
            finally:
                _INTERNAL.reset(internal)
                _MUTATION.reset(mutation)
            message.action_approve()
            if submission:
                self._website_submission_store(submission, message.id, order, session)
        return message.id

    def action_reply(self, body, attachments=None, reply_id=False, reaction=False):
        if self.channel_id.provider == 'website':
            if reaction:
                raise ValidationError(_('Invalid website reply.'))
            return self.website_action_reply(body, attachments=attachments, reply_id=reply_id)
        return super().action_reply(body, attachments, reply_id, reaction)

    def _website_detail(self, result):
        canonical = self.website_canonical_id or self
        orders = self.env['ab_crm_website_order'].search([
            ('account_id', '=', self.messaging_account_id.id),
            '|', ('conversation_id', '=', canonical.id), ('account_identity', '=', canonical.website_account_identity or '__unbound__'),
        ], order='id desc')
        identity = self.env['ab_crm_website_customer'].search([
            ('conversation_id', '=', canonical.id)], limit=1)
        latest = identity.latest_order_id or orders[:1]
        if canonical.website_phone:
            result['phone'] = canonical.website_phone
            result['display_phone'] = canonical.website_phone
        if latest:
            result['website_order'] = dict(latest._display_snapshot(latest.snapshot),
                revision=latest.revision, progress=latest.progress)
            result['phone'] = latest.phone
            result['display_phone'] = latest.phone
        if canonical.website_customer_name:
            result['phone'] = canonical.website_phone or ''
            result['display_phone'] = canonical.website_phone or ''
        eligible_orders = orders.filtered(lambda order: order.chat_ready and not order.chat_closed)
        if result.get('send_reason_code') == 'outgoing_disabled' and not self.env['ab_crm_message'].search_count([
            ('conversation_id', '=', self.id), ('direction', '=', 'in'),
            ('website_chat_event_id', '!=', False),
        ], limit=1):
            result['send_reason'] = ''
        sessions = self.env['ab_crm_website_session'].search([
            ('conversation_id', 'in', self._website_timeline_streams().ids),
            ('account_id', '=', self.messaging_account_id.id),
        ])
        result['website_has_closure_notice'] = bool(self.env['ab_crm_message'].search_count([('conversation_id', 'in', self._website_timeline_streams().ids), ('website_closure_notice', '=', True)], limit=1))
        result['website_session_ended'] = bool(sessions) and all(sessions.mapped('ended')) and not eligible_orders
        sessions = sessions.filtered(lambda session: not session.ended)
        result['website_reply_destinations'] = [
            {'key': 'order:' + str(order.id), 'label': order.public_reference or order.reference}
            for order in eligible_orders
        ] + [{'key': 'livechat:' + str(session.id), 'label': _('Floating chat') + ' · ' + session.session_uuid[:8]}
             for session in sessions]
        if len(eligible_orders) > 1:
            result['website_reply_orders'] = [{'id': order.id, 'reference': order.public_reference or order.reference}
                                             for order in eligible_orders]
        if result['website_reply_destinations']:
            try:
                target, session = self._website_reply_target()
                result['website_reply_order_id'] = target.id if target else False
                result['website_reply_session_id'] = session.id if session else False
            except UserError:
                pass
        messages = self.env['ab_crm_message'].browse([message['id'] for message in result['messages']])
        by_id = {message.id: message for message in messages}
        events = self.env['ab_crm_website_event'].search([
            ('account_id', '=', self.messaging_account_id.id),
            ('event_uuid', 'in', messages.filtered(lambda m: m.direction == 'in').mapped('provider_reference')),
            ('order_uuid', 'in', orders.mapped('order_uuid')),
        ])
        by_event = {event.event_uuid: event for event in events}
        by_uuid = {order.order_uuid: order for order in orders}
        for data in result['messages']:
            data['conversation_id'] = canonical.id
            data['website_receive_only'] = False
            message = by_id[data['id']]
            if message.website_closure_notice:
                data['body'] = message._website_closed_reason() or data['body']
            event = by_event.get(message.provider_reference)
            order = message.website_order_id or (by_uuid.get(event.order_uuid) if event else False)
            data['website_origin'] = (_('Order chat') + ' · ' + (order.public_reference or order.reference)) if order else (_('Floating chat') if message.website_session_id else '')
            data['website_origin_kind'] = 'order' if order else ('livechat' if message.website_session_id else False)
            if order:
                data['website_order_id'] = order.id
                data['website_order_reference'] = order.reference
            try:
                self._website_selected_target(message.id)
                data['actions']['reply'] = {'enabled': message.direction == 'in' and bool(result.get('can_send')),
                    'reason': result.get('send_reason') or ''}
            except (AccessError, UserError, ValidationError) as error:
                data['actions']['reply'] = {'enabled': False, 'reason': str(error)}
            if event and event.envelope['kind'] == 'order':
                data['website_order'] = dict(order._display_snapshot(event.envelope['payload']),
                    revision=event.revision)
                data['body'] = _('Website Order: %s') % data['website_order']['reference']
        header_order = orders.filtered(lambda order: order.id == result.get('website_reply_order_id'))[:1]
        if header_order:
            result['website_header_origin_kind'] = 'order'
            result['website_header_origin'] = _('Order chat') + ' · ' + (header_order.public_reference or header_order.reference)
        elif result.get('website_reply_session_id'):
            result['website_header_origin_kind'] = 'livechat'
            result['website_header_origin'] = _('Floating chat')
        else:
            last_message = self.env['ab_crm_message'].search(
                fields.Domain('conversation_id', 'in', self._website_timeline_streams().ids),
                order='id desc', limit=1)
            header_order = last_message.website_order_id
            if not header_order and last_message.provider_reference:
                event = self.env['ab_crm_website_event'].search(
                    fields.Domain('account_id', '=', self.messaging_account_id.id)
                    & fields.Domain('event_uuid', '=', last_message.provider_reference)
                    & fields.Domain('order_uuid', 'in', orders.mapped('order_uuid')), limit=1)
                header_order = orders.filtered(lambda order: order.order_uuid == event.order_uuid)[:1] if event else header_order
            result['website_header_origin_kind'] = 'order' if header_order else 'livechat'
            result['website_header_origin'] = (_('Order chat') + ' · ' + (header_order.public_reference or header_order.reference)) if header_order else _('Floating chat')
        return result

    def _website_navigation(self, result):
        for stream in result['streams']:
            if stream['provider'] == 'website':
                stream['shared_timeline'] = True
        return result

    def workspace_detail(self, *args, **kwargs):
        if self.channel_id.provider != 'website':
            return self._website_navigation(super().workspace_detail(*args, **kwargs))
        if self.website_canonical_id:
            return self.website_canonical_id.workspace_detail(*args, **kwargs)
        streams = self._website_timeline_streams()
        details = {
            stream.id: stream._website_detail(
                super(Conversation, stream).workspace_detail(*args, **kwargs)
            )
            for stream in streams
        }
        result = details[self.id]
        messages = sorted(
            [message for detail in details.values() for message in detail['messages']],
            key=lambda message: (message['timestamp'] or '', message['id']),
        )
        result['has_older'] = len(messages) > 50 or any(
            detail['has_older'] for detail in details.values()
        )
        result['messages'] = messages[:50] if kwargs.get('after_id') else messages[-50:]
        result['message_cursor'] = max(
            [detail['message_cursor'] or 0 for detail in details.values()], default=0
        )
        if kwargs.get('after_id') and result['messages']:
            result['message_cursor'] = max(message['id'] for message in result['messages'])
        unread = [detail['first_unread_message_id'] for detail in details.values()
                  if detail['first_unread_message_id']]
        result['first_unread_message_id'] = min(unread, default=False)
        result['unread_count'] = sum(detail['unread_count'] for detail in details.values())
        result['website_grouped'] = False
        return self._website_navigation(result)


class ChatterApi(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    @api.model
    def contact_accounts(self, token, contact_id):
        result = super().contact_accounts(token, contact_id)
        accounts = {}
        for row in result['accounts']:
            stream = self.env['ab_crm_conversation'].browse(row['id'])
            if stream.website_canonical_id:
                stream = stream.website_canonical_id
                stream._authorize('read')
                row = dict(row, id=stream.id, display_destination=stream._display_destination())
            accounts[row['id']] = row
        return {'accounts': list(accounts.values())}

    @api.model
    def contact_open(self, token, contact_id):
        result = super().contact_open(token, contact_id)
        stream = self.env['ab_crm_conversation'].browse(result['conversation_id'])
        if stream.website_canonical_id:
            stream.website_canonical_id._authorize('read')
            result['conversation_id'] = stream.website_canonical_id.id
        return result


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        return [*super()._get_translation_frontend_modules_name(), 'ab_crm_website']


class WebsiteOperation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    website_provider = fields.Selection(related='account_id.provider', string='Messaging provider')

    def action_website_retry(self):
        if not self._manager():
            raise AccessError(_('Only managers can retry website sends.'))
        self._staff_action()
        self._authorize('read')
        for record in self:
            record.account_id.lock_for_update()
            record.lock_for_update()
            record.invalidate_recordset()
            if record.account_id.provider != 'website' or record.state != 'review' or record.error_code not in ('unavailable', 'ambiguous', 'media'):
                raise UserError(_('Only uncertain website sends can be retried.'))
            record.message_id.conversation_id._owned()
            record.account_id._eligible_message(record.message_id)
            record.message_id._website_destination(record.account_id)
            record._change({'state': 'queued', 'attempt': record.attempt + 1, 'receipt': False,
                'lease_token': False, 'lease_until': False, 'error_code': 'none',
                'history': (record.sudo().history or []) + [{'action': 'website_same_token_retry',
                    'actor': self.env.uid, 'at': fields.Datetime.to_string(fields.Datetime.now())}]})
        return True
