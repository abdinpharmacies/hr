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
from ..protocol import validate


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
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can reconcile website chats.'))
        if type(account_id) is not int or type(limit) is not int or not 1 <= limit <= 500:
            raise ValidationError(_('Invalid website order.'))
        account = self.env['ab_crm_messaging_account'].browse(account_id).exists()
        account._authorize('read')
        if not account or account.provider != 'website':
            raise AccessError(_('Invalid website order.'))
        orders = self.search([('account_id', '=', account.id)], order='id', limit=limit + 1)
        orders._authorize('read')
        if len(orders) > limit:
            raise UserError(_('The reconciliation exceeds the configured order limit.'))
        groups = {}
        states = []
        for order in orders:
            phone = normalized_phone(order.phone or order.snapshot['customer']['phone'], account.company_id.country_id.code)
            key = phone or 'order:' + order.order_uuid
            groups.setdefault(key, self.browse())
            groups[key] |= order
            states.append((order.id, str(order.write_date), order.conversation_id.id,
                           order.website_customer_id.id, order.revision))
        conversations = orders.conversation_id.with_context(active_test=False)
        conversations._authorize('read')
        if any(c.channel_id != account.channel_id or c.branch_id != account.branch_id
               or c.company_id != account.company_id for c in conversations):
            raise AccessError(_('Invalid website order.'))
        identities = self.env['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', '=', account.channel_id.id),
            ('external_key', 'in', conversations.mapped('external_key')),
        ])
        snapshot = [states,
            [(c.id, c.customer_id.id, c.active, str(c.write_date)) for c in conversations.sorted('id')],
            [(i.id, i.customer_id.id, i.active, str(i.write_date)) for i in identities.sorted('id')]]
        result = []
        for key, group in groups.items():
            streams = group.conversation_id.sorted('id')
            saved = identities.filtered(lambda i: i.external_key in streams.mapped('external_key'))
            conflict = len(set(streams.mapped('customer_id').ids + [c.customer_id.id for c in streams])) > 1
            conflict = conflict or bool(saved.filtered(lambda i: i.active and i.customer_id != streams[:1].customer_id))
            conflict = conflict or (bool(saved.filtered('active')) and bool(saved.filtered(lambda i: not i.active)))
            canonical = streams[:1]
            result.append({'identity_key': key, 'order_ids': group.ids,
                           'canonical_id': canonical.id, 'alias_ids': (streams - canonical).ids,
                           'requires_review': bool(conflict)})
        return {'account_id': account.id, 'limit': limit, 'groups': result,
                'fingerprint': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()}

    @api.model
    def website_reconciliation_apply(self, account_id, fingerprint, limit=500):
        with self.env.cr.savepoint():
            return self._website_reconciliation_apply(account_id, fingerprint, limit)

    def _website_reconciliation_apply(self, account_id, fingerprint, limit):
        preview = self.website_reconciliation_preview(account_id, limit)
        account = self.env['ab_crm_messaging_account'].browse(account_id)
        account.branch_id.lock_for_update()
        account.branch_id.sudo().write({})
        self.env.invalidate_all()
        preview = self.website_reconciliation_preview(account_id, limit)
        if preview['fingerprint'] != fingerprint:
            raise UserError(_('The reconciliation changed. Preview it again.'))
        mutation, internal = _MUTATION.set(True), _INTERNAL.set(True)
        try:
            for group in preview['groups']:
                if group['requires_review']:
                    continue
                orders = self.browse(group['order_ids'])
                canonical = self.env['ab_crm_conversation'].browse(group['canonical_id'])
                aliases = self.env['ab_crm_conversation'].browse(group['alias_ids'])
                identity = self.env['ab_crm_website_customer'].sudo().search([
                    ('account_id', '=', account.id), ('identity_key', '=', group['identity_key']),
                    ('branch_id', '=', account.branch_id.id), ('company_id', '=', account.company_id.id),
                ], limit=1)
                if not identity:
                    identity = self.env['ab_crm_website_customer'].sudo().create({
                        'account_id': account.id, 'identity_key': group['identity_key'],
                        'conversation_id': canonical.id, 'branch_id': account.branch_id.id,
                        'company_id': account.company_id.id,
                    })
                for order in orders:
                    messages = self.env['ab_crm_message'].sudo().search([
                        ('conversation_id', 'in', (canonical | aliases).ids),
                        ('website_order_id', '=', False),
                    ])
                    event_refs = self.env['ab_crm_website_event'].search([
                        ('account_id', '=', account.id), ('order_uuid', '=', order.order_uuid),
                    ]).mapped('event_uuid')
                    incoming = messages.filtered(lambda m: m.direction == 'in' and m.provider_reference in event_refs)
                    outgoing = messages.filtered(lambda m: m.direction == 'out' and (
                        m.messaging_operation_ids.filtered(lambda op: op.destination == order.order_uuid)
                        or (not m.messaging_operation_ids and m.conversation_id.external_key == order.order_uuid)))
                    (incoming | outgoing).write({'website_order_id': order.id})
                historical_identities = orders.website_customer_id - identity
                historical_identities.sudo().write({'latest_order_id': False, 'conversation_id': canonical.id})
                orders.sudo().write({'conversation_id': canonical.id, 'website_customer_id': identity.id})
                aliases.sudo().write({'website_canonical_id': canonical.id})
                phone = group['identity_key'] if not group['identity_key'].startswith('order:') else False
                canonical.sudo().write({'website_phone': phone})
                latest = self.env['ab_crm_message'].sudo().search([
                    ('website_order_id', 'in', orders.ids), ('direction', '=', 'in'),
                ], order='id desc', limit=1)
                identity.write({'conversation_id': canonical.id,
                                'latest_order_id': (latest.website_order_id or orders[-1:]).id})
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        return preview

    def _display_delivery_address(self, address):
        lines = [' '.join(line.split()) for line in address.splitlines() if line.strip()]
        fallback = ' '.join(lines)
        country = self.env.ref('base.eg')
        country_names = {
            country.with_context(lang=language).name
            for language in ('en_US', 'ar_001')
        }
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
    def lease_outgoing(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider == 'website':
            return False
        return super().lease_outgoing(account_code, provider_account)

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        account = self._account(account_code, provider_account)
        if account.provider == 'website':
            self._operation(account, token, attempt)
            return False
        return super().authorize_send(account_code, provider_account, token, attempt, receipt)

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
            identity_key = ('order:' + event['order_uuid']) if order and not order.website_customer_id else (
                phone or 'order:' + event['order_uuid'])
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

    website_order_id = fields.Many2one('ab_crm_website_order', readonly=True, ondelete='restrict', index=True)

    @api.model_create_multi
    def create(self, values_list):
        if any('website_order_id' in values for values in values_list) and not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if 'website_order_id' in values and not _MUTATION.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def action_approve(self):
        website = self.filtered(lambda m: m.conversation_id.channel_id.provider == 'website')
        if website:
            website._staff_action()
            website._authorize()
            raise UserError(_('Website replies are disabled.'))
        return super().action_approve()


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    website_phone = fields.Char(readonly=True, index=True, copy=False)
    website_canonical_id = fields.Many2one('ab_crm_conversation', readonly=True, ondelete='restrict', index=True)


    @api.depends(
        'customer_id', 'branch_id', 'company_id', 'website_phone', 'channel_id.provider',
        'external_key', 'channel_id', 'website_canonical_id'
    )
    def _compute_customer_group_key(self):
        super()._compute_customer_group_key()
        for record in self:
            if record.channel_id.provider == 'website' and not record.customer_id:
                record.customer_group_key = (
                    f'{record.company_id.id}:{record.branch_id.id}:'
                    f'website-phone:{record.channel_id.id}:{record.website_phone}'
                    if record.website_phone else
                    f'{record.company_id.id}:{record.branch_id.id}:website-order:{record.external_key or record.id}'
                )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
            if ({'website_phone', 'website_canonical_id'} & values.keys() and not _MUTATION.get()) or (
                channel.provider == 'website'
                and values.get('customer_id')
                and not _WORKSPACE.get()
            ):
                raise AccessError(_('Use reviewed website customer linking.'))
        return super().create(values_list)

    def write(self, values):
        if ({'website_phone', 'website_canonical_id'} & values.keys() and not _MUTATION.get()) or (
            'customer_id' in values
            and not _WORKSPACE.get()
            and any(r.channel_id.provider == 'website' for r in self)
        ):
            raise AccessError(_('Use reviewed website customer linking.'))
        return super().write(values)

    def action_customer_link_candidates(self):
        if self.channel_id.provider != 'website':
            return super().action_customer_link_candidates()
        self.ensure_one()
        self._staff_action()
        self._authorize()
        self._workspace_scope()
        return {
            'phone': self.website_phone,
            'display_phone': self.website_phone,
            'contacts': [
                contact._directory_data()
                for contact in self._matching_saved_contacts(self.website_phone)
            ],
        }

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
        if self.channel_id.provider == 'website' and not self.customer_id:
            return self.website_canonical_id or self
        return super()._workspace_streams().filtered(lambda r: not r.website_canonical_id)

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
            order = self.env['ab_crm_website_order'].search(
                [('conversation_id', '=', self.id)], limit=1
            )
            if order:
                return '%s · %s' % (
                    order.snapshot['customer']['name'],
                    order.phone or order.snapshot['customer']['phone'],
                )
        return super()._provider_display_name()

    def action_identify(self, phone=False, customer_id=False, confirmed=False):
        if self.channel_id.provider == 'website' and not phone:
            self._owned()
            order = self.env['ab_crm_website_order'].search(
                [('conversation_id', '=', self.id)], limit=1
            )
            phone = order.phone
        return super().action_identify(phone, customer_id, confirmed)

    def _reply_eligibility(self):
        if self.channel_id.provider != 'website':
            return super()._reply_eligibility()
        self._authorize()
        self._workspace_scope()
        return 'outgoing_disabled', _('Website replies are disabled.')

    def website_action_reply(self, body, website_order_id=False, attachments=None, reply_id=False):
        self.ensure_one()
        if self.channel_id.provider != 'website':
            raise AccessError(_('Invalid website order.'))
        return self.action_reply(body, attachments=attachments, reply_id=reply_id)

    def action_reply(self, body, attachments=None, reply_id=False, reaction=False):
        if self.channel_id.provider == 'website':
            self._owned()
            raise UserError(_('Website replies are disabled.'))
        return super().action_reply(body, attachments, reply_id, reaction)

    def _website_detail(self, result):
        canonical = self.website_canonical_id or self
        orders = self.env['ab_crm_website_order'].search([
            ('conversation_id', '=', canonical.id),
            ('account_id', '=', self.messaging_account_id.id),
        ], order='id desc')
        identity = self.env['ab_crm_website_customer'].search([
            ('conversation_id', '=', canonical.id)], limit=1)
        latest = identity.latest_order_id or orders[:1]
        if latest:
            result['website_order'] = dict(latest._display_snapshot(latest.snapshot),
                revision=latest.revision, progress=latest.progress)
            result['phone'] = latest.phone
            result['display_phone'] = latest.phone
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
            data['website_receive_only'] = True
            message = by_id[data['id']]
            event = by_event.get(message.provider_reference)
            order = message.website_order_id or (by_uuid.get(event.order_uuid) if event else False)
            if order:
                data['website_order_id'] = order.id
                data['website_order_reference'] = order.reference
            if event and event.envelope['kind'] == 'order':
                data['website_order'] = dict(order._display_snapshot(event.envelope['payload']),
                    revision=event.revision)
                data['body'] = _('Website Order: %s') % data['website_order']['reference']
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
        result['website_grouped'] = True
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
