from contextvars import ContextVar

import phonenumbers

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_messaging.models.media import validate_media

_WORKSPACE = ContextVar('ab_crm_workspace', default=False)


def normalized_phone(value, country):
    if not country:
        return False
    try:
        number = phonenumbers.parse(value or '', country)
        if phonenumbers.is_valid_number(number):
            return phonenumbers.format_number(
                number, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    return False


class Scoped(models.AbstractModel):
    _inherit = 'ab_crm_scoped'

    def _staff_action(self):
        if self.env.user.has_group('base.group_system') and not self.env.user.has_group(
            'ab_crm_messaging.group_service'
        ):
            return
        return super()._staff_action()


class Branch(models.Model):
    _inherit = 'ab_crm_branch'

    replica_id = fields.Many2one(
        'ab_replica_db', ondelete='restrict', string='Intake Replica'
    )
    intake_store_id = fields.Many2one(
        related='replica_id.default_sales_store_id', string='Intake Store'
    )


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    @api.constrains('enabled', 'branch_id')
    def _check_workspace_mapping(self):
        for record in self:
            if record.enabled and record.provider == 'telegram':
                branch = record.branch_id.sudo()
                replica = branch.replica_id
                if (
                    not replica.active
                    or not replica.default_sales_store_id
                    or not replica.default_sales_store_id.active
                    or not replica.default_sales_store_id.allow_sale
                    or not replica.allowed_sales_store_ids
                    or replica.default_sales_store_id
                    not in replica.allowed_sales_store_ids
                    or not branch.company_id.country_id
                ):
                    raise ValidationError(
                        _(
                            'Configure the intake replica, default store and company country before activation.'
                        )
                    )


class Identity(models.Model):
    _inherit = 'ab_crm_identity'

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get():
            for values in values_list:
                channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
                channel.check_access('read')
                if channel.provider == 'telegram':
                    raise AccessError(
                        _('Use the workspace to confirm customer identity.')
                    )
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get() and any(
            record.channel_id.provider == 'telegram' for record in self
        ):
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        return super().write(values)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _receive_event_extra(self, account, event, message):
        result = super()._receive_event_extra(account, event, message)
        if message.telegram_contact_owned:
            message.conversation_id._resolve_ingested_contact(account, message)
        return result

    def _account(self, account_code, provider_account):
        account = super()._account(account_code, provider_account)
        account._check_workspace_mapping()
        return account


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    catalog_customer_id = fields.Many2one(
        'ab_customer', ondelete='restrict', readonly=True
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get() and any(
            v.get('catalog_customer_id') for v in values_list
        ):
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        return super().create(values_list)

    def write(self, values):
        if 'catalog_customer_id' in values and not _WORKSPACE.get():
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        return super().write(values)


class Message(models.Model):
    _inherit = 'ab_crm_message'

    def _display_status(self):
        self.ensure_one()
        operation = self.messaging_operation_ids[:1].sudo()
        state = operation.state or self.delivery_state
        status = {
            'draft': 'waiting',
            'queued': 'waiting',
            'approved': 'sending',
            'leased': 'sending',
            'received': 'sending',
            'accepted': 'sent',
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
            'cancelled': 'failed',
            'review': 'uncertain',
            'resolved': 'uncertain',
            'unknown': 'uncertain',
        }.get(state, 'uncertain')
        if self.direction != 'out':
            status = 'received'
        elif operation.attempt > 1:
            if status in ('waiting', 'sending'):
                status = 'retrying'
            elif status == 'failed':
                status = 'retry_failed'
        if self.conversation_id.channel_id.provider != 'whatsapp' and status in (
            'delivered',
            'read',
        ):
            status = 'sent'
        explanation = ''
        if status in ('failed', 'retry_failed'):
            explanation = (
                _('This attachment couldn’t be sent. Choose another file.')
                if operation.sudo().error_code == 'media'
                else _('The message was not sent. Try again when sending is available.')
            )
        elif status == 'uncertain':
            explanation = _(
                'Sending could not be confirmed. Ask a manager to check before sending again.'
            )
        retry = bool(
            self.direction == 'out'
            and operation.state == 'failed'
            and operation.retryable
            and operation.attempt < 3
            and operation.error_code in ('rate_limit', 'unavailable')
            and not operation.provider_reference
            and not self.conversation_id._reply_eligibility()[0]
        )
        return {
            'status': status,
            'explanation': explanation,
            'retry_operation_id': operation.id if retry else False,
            'status_at': fields.Datetime.to_string(
                operation.write_date or self.write_date
            ),
        }

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            for values in values_list:
                conversation = self.env['ab_crm_conversation'].browse(
                    values.get('conversation_id')
                )
                conversation.check_access('read')
                if conversation.channel_id.provider == 'telegram':
                    conversation._owned()
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            for conversation in self.conversation_id.filtered(
                lambda record: record.channel_id.provider == 'telegram'
            ):
                conversation._owned()
        return super().write(values)

    def action_approve(self):
        for conversation in self.conversation_id.filtered(
            lambda record: record.channel_id.provider == 'telegram'
        ):
            conversation._owned()
        result = super().action_approve()
        for message in self:
            message.conversation_id._log_workspace_action(
                'reaction' if message.reaction else 'reply', message_id=message.id
            )
        return result


class Operation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    error_code = fields.Selection(
        groups='ab_crm_core.group_manager,base.group_system,ab_crm_messaging.group_service'
    )
    provider_reference = fields.Char(
        groups='ab_crm_core.group_manager,base.group_system,ab_crm_messaging.group_service'
    )

    history = fields.Json(
        groups='ab_crm_core.group_manager,base.group_system,ab_crm_messaging.group_service'
    )
    review_note = fields.Text(groups='ab_crm_core.group_manager,base.group_system')
    reviewed_by = fields.Many2one(groups='ab_crm_core.group_manager,base.group_system')
    reviewed_at = fields.Datetime(groups='ab_crm_core.group_manager,base.group_system')

    def action_close_review(self, note=None):
        if not self.env.user.has_group(
            'base.group_system'
        ) and not self.env.user.has_group('ab_crm_core.group_manager'):
            raise AccessError(_('Only managers can review uncertain sends.'))
        return super().action_close_review(note)

    def action_cancel_unsent(self, reason):
        for conversation in self.message_id.conversation_id:
            conversation._owned()
        return super().action_cancel_unsent(reason)

    def action_retry(self):
        for operation in self:
            operation.message_id.conversation_id._owned()
            operation.lock_for_update()
            operation.invalidate_recordset()
            if operation.attempt >= 3 or operation.sudo().error_code == 'media':
                raise UserError(_('This message cannot be retried.'))
        result = super().action_retry()
        for operation in self:
            operation.message_id.conversation_id._log_workspace_action(
                'retry_message', message_id=operation.message_id.id
            )
        return result


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    assigned_employee_id = fields.Many2one('ab_hr_employee', readonly=True, copy=False)
    order_ids = fields.One2many('ab_crm_channel_order', 'conversation_id')
    contact_evidence_id = fields.Many2one('ab_crm_message', readonly=True, copy=False)
    catalog_match_state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('matched', 'Matched'),
            ('unmatched', 'No catalog match'),
            ('ambiguous', 'Ambiguous'),
            ('invalid', 'Invalid phone'),
            ('conflict', 'Identity conflict'),
        ],
        default='pending',
        readonly=True,
        copy=False,
    )
    review_catalog_customer_id = fields.Many2one(
        'ab_customer',
        groups='ab_crm_core.group_manager,base.group_system',
        copy=False,
    )
    catalog_candidate_ids = fields.Many2many(
        'ab_customer',
        compute='_compute_catalog_candidates',
        groups='ab_crm_core.group_manager,base.group_system',
    )
    staff_read_ids = fields.One2many(
        'ab_crm_workspace_read',
        'conversation_id',
        readonly=True,
        groups='ab_crm_core.group_manager,base.group_system',
    )
    confirmed_phone = fields.Char(readonly=True, copy=False)
    phone_confirmed_by = fields.Many2one('res.users', readonly=True, copy=False)
    phone_confirmed_at = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        protected = {
            'assigned_employee_id',
            'confirmed_phone',
            'phone_confirmed_by',
            'phone_confirmed_at',
            'contact_evidence_id',
            'catalog_match_state',
        }
        if not _WORKSPACE.get() and not _INTERNAL.get():
            for values in values_list:
                channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
                channel.check_access('read')
                if values.get('customer_id') and channel.provider == 'telegram':
                    raise AccessError(
                        _('Use the workspace to confirm customer identity.')
                    )
        if not _WORKSPACE.get() and any(protected & v.keys() for v in values_list):
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        values_list = (
            [
                dict(
                    v,
                    **{
                        key: ('pending' if key == 'catalog_match_state' else False)
                        for key in protected
                    }
                )
                for v in values_list
            ]
            if not _WORKSPACE.get()
            else values_list
        )
        return super().create(values_list)

    def write(self, values):
        if (
            'customer_id' in values
            and not _WORKSPACE.get()
            and any(record.channel_id.provider == 'telegram' for record in self)
        ):
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        if (
            not _WORKSPACE.get()
            and {
                'assigned_employee_id',
                'confirmed_phone',
                'phone_confirmed_by',
                'phone_confirmed_at',
                'contact_evidence_id',
                'catalog_match_state',
            }
            & values.keys()
        ):
            raise AccessError(_('Use the workspace to confirm customer identity.'))
        return super().write(values)

    def _workspace_actor(self):
        return self.env['ab_crm_chatter_api']._session(
            self.env.context.get('ab_chatter_session_token')
        )

    def _workspace_scope(self):
        self.ensure_one()
        self._authorize('read')
        session = self._workspace_actor()
        branch = self.branch_id
        if branch.company_id != session.company_id:
            raise AccessError(_('The selected company or branch is not allowed.'))
        replica = branch.replica_id
        if (
            not replica.active
            or not replica.default_sales_store_id
            or not replica.default_sales_store_id.active
            or not replica.default_sales_store_id.allow_sale
            or not replica.allowed_sales_store_ids
            or replica.default_sales_store_id not in replica.allowed_sales_store_ids
            or not branch.company_id.country_id
        ):
            raise UserError(
                _(
                    'Configure the intake replica, default store and company country before activation.'
                )
            )
        stores = replica.allowed_sales_store_ids.filtered(
            lambda r: r.active and r.allow_sale
        )
        self.env['ab_crm_chatter_api']._branch_scope(session, branch)
        profile = session._get_pos_profile()
        if profile.pos_allowed_store_ids:
            stores &= profile.pos_allowed_store_ids
        user = self.env.user
        if not user.has_group('base.group_system') and not user.has_group(
            'ab_sales.group_ab_sales_manager'
        ):
            departments = user.sudo().ab_department_ids
            user_stores = (
                departments.store_id
                | user.sudo().ab_employee_ids.department_id.store_id
            )
            if user_stores:
                stores &= user_stores
            elif not user.has_group('ab_sales.group_call_center'):
                stores = stores.browse()
        stores.check_access('read')
        if not stores:
            raise AccessError(_('The selected company or branch is not allowed.'))
        return session, stores

    def _owned(self):
        self.ensure_one()
        self._authorize()
        session, stores = self._workspace_scope()
        self.messaging_account_id.lock_for_update()
        self.lock_for_update()
        return session, stores

    def action_claim(self):
        self._owned()
        return True

    def _customer_display_name(self):
        self.ensure_one()
        customer_name = self.customer_id.name
        if customer_name in (
            self.external_key,
            self.customer_id.phone,
            self.confirmed_phone,
        ):
            customer_name = False
        return (
            self.customer_id.chatter_name
            or self.customer_id.catalog_customer_id.name
            or customer_name
            or self.telegram_profile_name
            or self.telegram_username
            or self.confirmed_phone
            or self.customer_id.phone
            or _('Unidentified sender')
        )

    def _resolve_ingested_contact(self, account, message):
        self.ensure_one()
        if (
            not _INTERNAL.get()
            or account.service_user_id.id != self.env.uid
            or account.company_id not in self.env.companies
            or self.branch_id != account.branch_id
            or self.company_id != account.company_id
            or self.channel_id != account.channel_id
            or message.conversation_id != self
            or not message.telegram_contact_owned
        ):
            raise AccessError(_('The messaging account is not authorized.'))
        phone = normalized_phone(
            message.telegram_phone, self.company_id.country_id.code
        )
        token = _WORKSPACE.set(True)
        try:
            self.write({'contact_evidence_id': message.id})
            if not phone:
                self.write({'catalog_match_state': 'invalid'})
                return
            stores = account.branch_id.replica_id.allowed_sales_store_ids.filtered(
                lambda store: store.active and store.allow_sale
            )
            try:
                candidates = self._catalog_phone_candidates(phone, stores)
            except UserError:
                self._link_contact(phone, self.env['ab_customer'], verified=True)
                self.write({'catalog_match_state': 'ambiguous'})
                return
            self._link_contact(phone, candidates, verified=True)
        finally:
            _WORKSPACE.reset(token)

    def _reply_eligibility(self):
        self.ensure_one()
        try:
            self._authorize()
            self._workspace_scope()
        except (AccessError, UserError) as error:
            return 'session_required', str(error)
        if self.channel_id.provider != 'telegram':
            return 'channel_deferred', _('This channel integration is deferred.')
        account = self.messaging_account_id
        if not account:
            return 'account_missing', _('Messaging is disabled for this account.')
        code, reason = account._queue_eligibility(self)
        if code:
            return code, reason
        try:
            account._eligible(self, _('Attachment'))
        except (AccessError, UserError) as error:
            return 'provider_restriction', str(error)
        return False, False

    def action_reply(self, body, attachments=None, reply_id=False, reaction=False):
        self._owned()
        code, reason = self._reply_eligibility()
        if code:
            raise UserError(reason)
        self.messaging_account_id._eligible(self, body or _('Attachment'))
        attachments = attachments or []
        if (
            not isinstance(attachments, list)
            or len(attachments) > 4
            or (reaction and (attachments or reaction not in ('👍', '❤', '👎')))
        ):
            raise ValidationError(_('Invalid media.'))
        reply = (
            self.env['ab_crm_message'].browse(reply_id).exists()
            if reply_id
            else self.env['ab_crm_message']
        )
        if reply:
            reply.check_access('read')
            if reply.conversation_id != self or not reply.provider_reference:
                raise AccessError(_('Select a message from this conversation.'))
        if reaction and not reply:
            raise ValidationError(_('Select a message from this conversation.'))
        for attachment in attachments:
            validate_media(attachment, attachment.get('data'), translate=self.env._)
        if attachments and len(body or '') > 1024:
            raise ValidationError(_('Media captions must not exceed 1024 characters.'))
        ids = []
        with self.env.cr.savepoint():
            for attachment in attachments or [None]:
                token = _INTERNAL.set(True)
                try:
                    message = self.env['ab_crm_message'].create(
                        {
                            'conversation_id': self.id,
                            'branch_id': self.branch_id.id,
                            'company_id': self.company_id.id,
                            'direction': 'out',
                            'body': reaction or body or _('Attachment'),
                            'reply_reference': reply.provider_reference or '',
                            'reaction': reaction or '',
                        }
                    )
                    if attachment:
                        self.env['ab_crm_message_media'].sudo().create(
                            {
                                'message_id': message.id,
                                'branch_id': self.branch_id.id,
                                'company_id': self.company_id.id,
                                **{
                                    key: attachment[key]
                                    for key in (
                                        'kind',
                                        'name',
                                        'mimetype',
                                        'size',
                                        'data',
                                    )
                                },
                                'duration': attachment.get('duration', 0),
                                'state': 'ready',
                            }
                        )
                finally:
                    _INTERNAL.reset(token)
                message.action_approve()
                ids.append(message.id)
        return ids[0] if len(ids) == 1 else ids

    def action_request_contact(self):
        self._owned()
        return super().action_request_contact()

    def _phone_candidates(self, phone):
        session, stores = self._workspace_scope()
        return self._catalog_phone_candidates(phone, stores)

    def _catalog_phone_candidates(self, phone, stores):
        digits = ''.join(c for c in phone if c.isdigit())[-7:]
        pattern = '%' + '%'.join(digits) + '%'
        candidates = self.env['ab_customer'].search(
            [
                ('default_store_id', 'in', stores.ids),
                '|',
                '|',
                ('mobile_phone', 'ilike', pattern),
                ('work_phone', 'ilike', pattern),
                ('delivery_phone', 'ilike', pattern),
            ],
            limit=1001,
        )
        if len(candidates) > 1000:
            raise UserError(
                _('Too many phone candidates. Review the customer catalog first.')
            )
        country = self.company_id.country_id.code
        return candidates.filtered(
            lambda r: phone
            in [
                normalized_phone(r[f], country)
                for f in ('mobile_phone', 'work_phone', 'delivery_phone')
            ]
        )

    def action_identify(self, phone=False, customer_id=False, confirmed=False):
        self._owned()
        contact = self.message_ids.filtered(lambda m: m.telegram_phone)[-1:]
        verified = bool(
            contact
            and contact.telegram_contact_owned
            and (not phone or phone == contact.telegram_phone)
        )
        phone = normalized_phone(
            phone or contact.telegram_phone, self.company_id.country_id.code
        )
        if not phone:
            raise UserError(_('Enter a valid customer phone number.'))
        if not verified and not confirmed:
            raise UserError(
                _('Confirm typed or third-party phone numbers before linking.')
            )
        candidates = self._phone_candidates(phone)
        if len(candidates) > 1 and not customer_id:
            return {'candidates': [{'id': r.id, 'name': r.name} for r in candidates]}
        selected = (
            candidates.filtered(lambda r: r.id == customer_id)
            if customer_id
            else candidates[:1]
        )
        if customer_id and not selected:
            raise AccessError(_('Select an authorized matching customer.'))
        return self._link_contact(phone, selected, verified=verified)

    def _link_contact(self, phone, candidates, verified=False):
        self.ensure_one()
        token = _WORKSPACE.set(True)
        try:
            identity = (
                self.env['ab_crm_identity']
                .with_context(active_test=False)
                .search(
                    [
                        ('channel_id', '=', self.channel_id.id),
                        ('external_key', '=', self.external_key),
                    ],
                    limit=1,
                )
            )
            if identity and identity.customer_id.phone != phone:
                self.write({'catalog_match_state': 'conflict'})
                return {'candidates': []}
            selected = candidates if len(candidates) == 1 else candidates.browse()
            customer = identity.customer_id or self.customer_id
            if not customer or customer.phone != phone:
                customer = self.env['ab_crm_customer'].search(
                    [
                        ('branch_id', '=', self.branch_id.id),
                        ('company_id', '=', self.company_id.id),
                        ('phone', '=', phone),
                        ('catalog_customer_id', '=', selected.id),
                    ],
                    limit=1,
                )
            if not customer:
                customer = self.env['ab_crm_customer'].create(
                    {
                        'name': selected.name or phone,
                        'phone': phone,
                        'address': selected.address or False,
                        'catalog_customer_id': selected.id,
                        'branch_id': self.branch_id.id,
                        'company_id': self.company_id.id,
                    }
                )
            elif selected and not customer.catalog_customer_id:
                customer.write(
                    {
                        'catalog_customer_id': selected.id,
                        'name': selected.name,
                        'address': customer.address or selected.address,
                    }
                )
            values = {
                'customer_id': customer.id,
                'catalog_match_state': (
                    'ambiguous'
                    if len(candidates) > 1
                    else 'matched' if selected else 'unmatched'
                ),
            }
            if verified:
                values.update(
                    confirmed_phone=phone,
                    phone_confirmed_by=self.env.uid,
                    phone_confirmed_at=fields.Datetime.now(),
                )
            self.write(values)
            if verified and not identity:
                self.env['ab_crm_identity'].create(
                    {
                        'customer_id': customer.id,
                        'channel_id': self.channel_id.id,
                        'external_key': self.external_key,
                        'branch_id': self.branch_id.id,
                        'company_id': self.company_id.id,
                    }
                )
        finally:
            _WORKSPACE.reset(token)
        return {
            'customer_id': customer.id,
            'phone': phone,
            'candidates': (
                [{'id': record.id, 'name': record.name} for record in candidates]
                if len(candidates) > 1
                else []
            ),
        }

    def _compute_catalog_candidates(self):
        for record in self:
            record._authorize('read')
            stores = record.branch_id.replica_id.allowed_sales_store_ids.filtered(
                lambda store: store.active and store.allow_sale
            )
            record.catalog_candidate_ids = (
                record._catalog_phone_candidates(record.confirmed_phone, stores)
                if record.confirmed_phone
                else self.env['ab_customer']
            )

    def action_review_catalog(self):
        self.ensure_one()
        self._staff_action()
        self._authorize()
        if not self._manager():
            raise AccessError(_('Only CRM managers can review contact matches.'))
        self.messaging_account_id.lock_for_update()
        self.lock_for_update()
        phone = self.confirmed_phone
        if not phone:
            raise UserError(_('A self-shared contact is required for catalog review.'))
        stores = self.branch_id.replica_id.allowed_sales_store_ids.filtered(
            lambda store: store.active and store.allow_sale
        )
        candidates = self._catalog_phone_candidates(phone, stores)
        selected = candidates.filtered(
            lambda record: record == self.review_catalog_customer_id
        )
        if not selected:
            raise AccessError(_('Select an authorized matching customer.'))
        if (
            self.customer_id.catalog_customer_id
            and self.customer_id.catalog_customer_id != selected
        ):
            raise UserError(
                _('This Telegram identity is already linked to another contact.')
            )
        self._link_contact(phone, selected, verified=True)
        return True

    def _log_workspace_action(self, action, message_id=False):
        session, stores = self._workspace_scope()
        self.env['ab_crm_workspace_audit'].sudo().create(
            {
                'conversation_id': self.id,
                'message_id': message_id,
                'branch_id': self.branch_id.id,
                'company_id': session.company_id.id,
                'user_id': self.env.uid,
                'employee_id': session.employee_id.id,
                'action': action,
            }
        )

    def workspace_focus(self, message_id):
        self.ensure_one()
        self._workspace_scope()
        message = self.env['ab_crm_message'].browse(message_id).exists()
        message.check_access('read')
        if not message or message.conversation_id != self or message.direction != 'in':
            raise AccessError(_('Select a message from this conversation.'))
        result = self.workspace_detail(before_id=message.id + 1)
        result['focus_message_id'] = message.id
        return result

    def action_new_order(self):
        self._owned()
        order = self.env['ab_crm_channel_order'].create({'conversation_id': self.id})
        return order.id

    @api.model
    def workspace_inbox(self, query='', before_id=False):
        session = self._workspace_actor()
        branches = self.env['ab_crm_chatter_api']._directory_branches(session)
        domain = [
            ('company_id', '=', session.company_id.id),
            ('branch_id', 'in', branches.ids),
        ]
        if query:
            if not isinstance(query, str) or len(query) > 200:
                raise ValidationError(_('Invalid conversation search.'))
            domain += [
                '|',
                '|',
                '|',
                '|',
                '|',
                '|',
                ('telegram_profile_name', 'ilike', query),
                ('confirmed_phone', 'ilike', query),
                ('name', 'ilike', query),
                ('customer_id.name', 'ilike', query),
                ('customer_id.chatter_name', 'ilike', query),
                ('customer_id.chatter_phone', 'ilike', query),
                ('customer_id.phone', 'ilike', query),
            ]
        if before_id:
            domain.append(('id', '<', int(before_id)))
        conversations = self.search(domain, limit=50, order='id desc')
        positions = (
            self.env['ab_crm_workspace_read']
            .sudo()
            .search(
                [
                    ('conversation_id', 'in', conversations.ids),
                    ('user_id', '=', self.env.uid),
                    ('employee_id', '=', session.employee_id.id),
                ]
            )
        )
        seen = {r.conversation_id.id: r.last_message_id.id for r in positions}
        result = []
        for record in conversations:
            messages = record.message_ids.filtered(lambda m: m.direction == 'in')
            channels = {record.channel_id.provider} if messages else set()
            if record.customer_id:
                contacted = self.search(
                    [
                        ('customer_id', '=', record.customer_id.id),
                        ('message_ids.direction', '=', 'in'),
                    ]
                )
                channels.update(contacted.channel_id.mapped('provider'))
            result.append(
                {
                    'id': record.id,
                    'customer_id': record.customer_id.id,
                    'name': record._customer_display_name(),
                    'provider': record.channel_id.provider,
                    'channels': sorted(channels),
                    'preview': record.message_ids.sorted('id')[-1:].body or '',
                    'unread': len(
                        messages.filtered(lambda m: m.id > seen.get(record.id, 0))
                    ),
                }
            )
        return result

    def workspace_detail(
        self, before_id=False, after_id=False, query='', mark_read=True
    ):
        self.ensure_one()
        session, stores = self._workspace_scope()
        send_code, send_reason = self._reply_eligibility()
        domain = [('conversation_id', '=', self.id)]
        if query:
            domain.append(('body', 'ilike', str(query)[:200]))
        if before_id:
            domain.append(('id', '<', int(before_id)))
        if after_id:
            domain.append(('id', '>', int(after_id)))
        messages = (
            self.env['ab_crm_message']
            .search(domain, limit=50, order='id asc' if after_id else 'id desc')
            .sorted('id')
        )
        events = self.env['ab_crm_messaging_event'].search(
            [('message_id', 'in', messages.ids)]
        )
        timestamps = {event.message_id.id: event.provider_timestamp for event in events}
        has_older = bool(
            messages
            and self.env['ab_crm_message'].search_count(
                [('conversation_id', '=', self.id), ('id', '<', messages[0].id)],
                limit=1,
            )
        )
        streams = (
            self.search(
                [
                    ('customer_id', '=', self.customer_id.id),
                    ('message_ids.direction', '=', 'in'),
                ]
            )
            if self.customer_id
            else self
        )
        streams = streams.filtered(
            lambda record: any(m.direction == 'in' for m in record.message_ids)
        )
        position = (
            self.env['ab_crm_workspace_read']
            .sudo()
            .search(
                [
                    ('conversation_id', '=', self.id),
                    ('employee_id', '=', session.employee_id.id),
                    ('user_id', '=', self.env.uid),
                ],
                limit=1,
            )
        )
        if position and mark_read and not query:
            if messages and messages[-1].id > position.last_message_id.id:
                position.lock_for_update()
                position.invalidate_recordset()
                position.write(
                    {
                        'last_message_id': messages[-1].id,
                        'read_at': fields.Datetime.now(),
                    }
                )
        elif not position and messages and mark_read and not query:
            self.lock_for_update()
            self.write({})
            self.env['ab_crm_workspace_read'].sudo().create(
                {
                    'conversation_id': self.id,
                    'last_message_id': messages[-1:].id,
                    'employee_id': session.employee_id.id,
                    'read_at': fields.Datetime.now(),
                }
            )
        return {
            'id': self.id,
            'candidates': [],
            'can_send': not send_code,
            'send_reason_code': send_code or '',
            'send_reason': send_reason or '',
            'gateway_status': 'unknown',
            'sending_enabled': self.messaging_account_id.outgoing_enabled,
            'capabilities': {
                'media': self.channel_id.provider == 'telegram',
                'reactions': self.channel_id.provider == 'telegram',
                'customer_read': self.channel_id.provider == 'whatsapp'
                and self.messaging_account_id._status_allowed('read'),
                'customer_delivered': self.channel_id.provider == 'whatsapp'
                and self.messaging_account_id._status_allowed('delivered'),
            },
            'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'has_older': has_older,
            'streams': [
                {'id': r.id, 'provider': r.channel_id.provider} for r in streams
            ],
            'name': self._customer_display_name(),
            'phone': self.customer_id.chatter_phone
            or self.confirmed_phone
            or self.customer_id.phone
            or '',
            'owned': True,
            'provider': self.channel_id.provider,
            'stores': [{'id': r.id, 'name': r.name, 'code': r.code} for r in stores],
            'messages': [
                {
                    'id': m.id,
                    'body': m.body,
                    'direction': m.direction,
                    **m._display_status(),
                    'timestamp': fields.Datetime.to_string(
                        timestamps.get(m.id) or m.create_date
                    ),
                    'phone': m.telegram_phone or '',
                    'owned': m.telegram_contact_owned,
                    'can_reply': bool(m.provider_reference),
                    'is_reply': bool(m.reply_reference),
                    'reaction': m.reaction or '',
                    'media': [
                        {'id': a.id, 'name': a.name, 'kind': a.kind, 'state': a.state}
                        for a in m.media_ids
                    ],
                }
                for m in messages
            ],
            'orders': [
                {
                    'id': o.id,
                    'name': o.display_name,
                    'state': o.state,
                    'revision': o.revision,
                }
                for o in self.order_ids
            ],
        }


class ReadPosition(models.Model):
    _name = 'ab_crm_workspace_read'
    _description = 'Conversation Read Position'

    conversation_id = fields.Many2one(
        'ab_crm_conversation', required=True, ondelete='restrict'
    )
    user_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user
    )
    branch_id = fields.Many2one(related='conversation_id.branch_id', store=True)
    company_id = fields.Many2one(related='conversation_id.company_id', store=True)
    last_message_id = fields.Many2one('ab_crm_message', ondelete='restrict')
    employee_id = fields.Many2one('ab_hr_employee', ondelete='restrict')
    read_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    _reader_unique = models.Constraint(
        'UNIQUE(conversation_id, user_id, employee_id)',
        'Only one read position per user is allowed.',
    )

    @api.model_create_multi
    def create(self, values_list):
        return super().create(
            [dict(values, read_at=fields.Datetime.now()) for values in values_list]
        )

    def write(self, values):
        if values.keys() - {'last_message_id', 'read_at'}:
            raise AccessError(_('Invalid read position.'))
        return super().write(dict(values, read_at=fields.Datetime.now()))

    @api.constrains('conversation_id', 'user_id', 'employee_id', 'last_message_id')
    def _check_reader(self):
        for record in self:
            record.conversation_id._authorize('read')
            session, stores = record.conversation_id._workspace_scope()
            if (
                record.employee_id != session.employee_id
                or record.user_id != self.env.user
                or (
                    record.last_message_id
                    and record.last_message_id.conversation_id != record.conversation_id
                )
            ):
                raise AccessError(_('Invalid read position.'))
