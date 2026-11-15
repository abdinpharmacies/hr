import re
from copy import deepcopy
from urllib.parse import urlsplit

from lxml import html
from odoo.tools import html2plaintext
from uuid import UUID

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError
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
        if not code and self.provider == 'website' and not self.outgoing_enabled:
            return 'outgoing_disabled', _('Website replies are disabled.')
        return code, reason


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
    def receive_website_event(self, account_code, provider_account, event):
        account = self._account(account_code, provider_account)
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
        account.branch_id.lock_for_update()
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
            super().receive_event(
                account_code,
                provider_account,
                {
                    'id': event['event_uuid'],
                    'sender': event['order_uuid'],
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
                            ('external_key', '=', event['order_uuid']),
                        ],
                        limit=1,
                    )
                )
                phone = normalized_phone(
                    payload['customer']['phone'], account.company_id.country_id.code
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
                        % (payload['reference'], phone or payload['customer']['name']),
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

    def action_approve(self):
        website = self.filtered(
            lambda m: m.conversation_id.channel_id.provider == 'website'
        )
        website._staff_action()
        website._authorize()
        website.lock_for_update()
        for message in website:
            message.conversation_id.messaging_account_id._eligible_message(message)
        result = super().action_approve()
        mutation = _MUTATION.set(True)
        try:
            for message in website:
                self.env['ab_crm_messaging_operation'].sudo().create(
                    {
                        'account_id': message.conversation_id.messaging_account_id.id,
                        'message_id': message.id,
                        'body': message.body,
                        'destination': message.conversation_id.external_key,
                        'branch_id': message.branch_id.id,
                        'company_id': message.company_id.id,
                        'approved_by': self.env.uid,
                        'approved_at': message.approved_at,
                    }
                )
                message._internal_write({'delivery_state': 'unknown'})
        finally:
            _MUTATION.reset(mutation)
        return result


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    website_phone = fields.Char(readonly=True, index=True, copy=False)

    @api.depends(
        'customer_id', 'branch_id', 'company_id', 'website_phone', 'channel_id.provider',
        'external_key'
    )
    def _compute_customer_group_key(self):
        super()._compute_customer_group_key()
        for record in self:
            if record.channel_id.provider == 'website' and not record.customer_id:
                record.customer_group_key = (
                    f'{record.company_id.id}:{record.branch_id.id}:'
                    f'website-phone:{record.website_phone}'
                    if record.website_phone else
                    f'{record.company_id.id}:{record.branch_id.id}:website-order:{record.external_key or record.id}'
                )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
            if ('website_phone' in values and not _MUTATION.get()) or (
                channel.provider == 'website'
                and values.get('customer_id')
                and not _WORKSPACE.get()
            ):
                raise AccessError(_('Use reviewed website customer linking.'))
        return super().create(values_list)

    def write(self, values):
        if ('website_phone' in values and not _MUTATION.get()) or (
            'customer_id' in values
            and not _WORKSPACE.get()
            and any(r.channel_id.provider == 'website' for r in self)
        ):
            raise AccessError(_('Use reviewed website customer linking.'))
        return super().write(values)

    def action_customer_link_candidates(self):
        if self.channel_id.provider != 'website':
            return super().action_customer_link_candidates()
        self._owned()
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
        domain = super()._workspace_inbox_domain(query)
        session = self._workspace_actor()
        phone = (
            normalized_phone(query, session.company_id.country_id.code)
            if query
            else False
        )
        if phone:
            scope = fields.Domain(super()._workspace_inbox_domain(''))
            return list(
                fields.Domain(domain)
                | (scope & fields.Domain('website_phone', '=', phone))
            )
        return domain

    def _website_timeline_streams(self):
        self.ensure_one()
        self._workspace_scope()
        if self.customer_id:
            return self._workspace_streams().filtered(lambda record: record.channel_id.provider == 'website')
        candidates = self.search([
            ('company_id', '=', self.company_id.id),
            ('branch_id', '=', self.branch_id.id),
            ('website_phone', '=', self.website_phone),
            ('customer_id', '=', False),
            ('channel_id.provider', '=', 'website'),
            ('channel_id.active', '=', True),
        ]) if self.website_phone else self
        allowed = self.browse()
        for conversation in candidates:
            try:
                conversation._workspace_scope()
            except (AccessError, UserError):
                continue
            if conversation.messaging_account_id:
                allowed |= conversation
        return allowed

    def _workspace_streams(self):
        if self.channel_id.provider == 'website' and not self.customer_id:
            return self._website_timeline_streams()
        return super()._workspace_streams()

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
            order = self.env['ab_crm_website_order'].search(
                [('conversation_id', '=', self.id)], limit=1)
            if order:
                return order.reference
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
        if self.channel_id.provider != "website":
            return super()._reply_eligibility()
        self._authorize()
        self._workspace_scope()
        if not self.messaging_account_id:
            return "account_missing", _("Website intake is disabled.")
        return self.messaging_account_id._queue_eligibility(self)

    def action_reply(self, body, attachments=None, reply_id=False, reaction=False):
        if self.channel_id.provider == "website" and (
            attachments or reaction or reply_id
        ):
            raise ValidationError(_("Website chat supports text only."))
        return super().action_reply(body, attachments, reply_id, reaction)

    def _website_detail(self, result):
        order = self.env['ab_crm_website_order'].search(
            [('conversation_id', '=', self.id)], limit=1
        )
        if order:
            result['website_order'] = dict(
                order._display_snapshot(order.snapshot), revision=order.revision, progress=order.progress
            )
            result['phone'] = order.phone
            result['display_phone'] = order.phone
            messages = self.env['ab_crm_message'].browse(
                [message['id'] for message in result['messages']]
            )
            references = {
                message.id: message.provider_reference
                for message in messages
                if message.direction == 'in'
            }
            events = self.env['ab_crm_website_event'].search(
                [
                    ('account_id', '=', order.account_id.id),
                    ('order_uuid', '=', order.order_uuid),
                    ('event_uuid', 'in', list(references.values())),
                ]
            )
            quotations = {
                event.event_uuid: dict(
                    order._display_snapshot(event.envelope['payload']), revision=event.revision
                )
                for event in events
                if event.envelope['kind'] == 'order'
            }
            for message in result['messages']:
                message['conversation_id'] = self.id
                quotation = quotations.get(references.get(message['id']))
                if quotation:
                    message['website_order'] = quotation
                    message['body'] = _('Website Order: %s') % quotation['reference']
        return result

    def _website_navigation(self, result):
        for stream in result['streams']:
            if stream['provider'] == 'website':
                stream['shared_timeline'] = True
        return result

    def workspace_detail(self, *args, **kwargs):
        if self.channel_id.provider != 'website':
            return self._website_navigation(super().workspace_detail(*args, **kwargs))
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
        order_references = {
            key: detail['website_order']['reference']
            for key, detail in details.items() if detail.get('website_order')
        }
        for stream in result['streams']:
            if stream['id'] in order_references:
                stream['display_destination'] = order_references[stream['id']]
        result['website_grouped'] = True
        return self._website_navigation(result)


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        return [*super()._get_translation_frontend_modules_name(), 'ab_crm_website']
