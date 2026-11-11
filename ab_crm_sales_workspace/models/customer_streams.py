import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .workspace import _WORKSPACE, normalized_phone, display_phone


class Identity(models.Model):
    _inherit = 'ab_crm_identity'

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get():
            for values in values_list:
                channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
                channel.check_access('read')
                if channel.provider == 'whatsapp':
                    raise AccessError(_('Use reviewed customer linking for this identity.'))
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get() and any(r.channel_id.provider == 'whatsapp' for r in self):
            raise AccessError(_('Use reviewed customer linking for this identity.'))
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    customer_group_key = fields.Char(compute='_compute_customer_group_key', store=True, index=True)

    @api.depends('customer_id', 'branch_id', 'company_id')
    def _compute_customer_group_key(self):
        for record in self:
            owner = f'customer:{record.customer_id.id}' if record.customer_id else f'conversation:{record.id}'
            record.customer_group_key = f'{record.company_id.id}:{record.branch_id.id}:{owner}'

    @api.model_create_multi
    def create(self, values_list):
        if any('customer_group_key' in values for values in values_list):
            raise AccessError(_('Use reviewed customer linking for this identity.'))
        if not _WORKSPACE.get():
            from odoo.addons.ab_crm_core.models.core import _INTERNAL
            for values in values_list:
                if values.get('customer_id') and not _INTERNAL.get():
                    channel = self.env['ab_crm_channel'].browse(values.get('channel_id'))
                    channel.check_access('read')
                    if channel.provider == 'whatsapp':
                        raise AccessError(_('Use reviewed customer linking for this identity.'))
        return super().create(values_list)

    def write(self, values):
        if 'customer_group_key' in values:
            raise AccessError(_('Use reviewed customer linking for this identity.'))
        if 'customer_id' in values and not _WORKSPACE.get() and any(
            r.channel_id.provider == 'whatsapp' for r in self
        ):
            raise AccessError(_('Use reviewed customer linking for this identity.'))
        return super().write(values)

    def action_identify(self, phone=False, customer_id=False, confirmed=False):
        if self.channel_id.provider == 'whatsapp':
            raise AccessError(_('Use reviewed customer linking for this identity.'))
        saved = self._matching_saved_contacts(normalized_phone(phone, self.company_id.country_id.code) if phone else self._verified_sender_phone())
        if saved and not self.customer_id and not customer_id and (not phone or normalized_phone(phone, self.company_id.country_id.code) == self._verified_sender_phone()):
            self._auto_link_matching_customer()
            if self.customer_id == saved:
                self._owned()
                return {'customer_id': saved.id, 'phone': self._verified_sender_phone(), 'candidates': []}
        if saved and not self.customer_id:
            self._owned()
            raise UserError(_('Review the matching saved contact before linking this identity.'))
        return super().action_identify(phone, customer_id, confirmed)

    def _customer_link_scope(self, customer_id):
        self.ensure_one()
        self._staff_action()
        self._authorize()
        session, stores = self._workspace_scope()
        if type(customer_id) is not int or customer_id <= 0:
            raise UserError(_('Select a saved contact.'))
        customer = self.env['ab_crm_customer'].browse(customer_id).exists()
        customer._authorize('read')
        account = self.messaging_account_id
        account._authorize('read')
        if not customer or not customer.active:
            raise UserError(_('Select a saved contact.'))
        if not account or not self.active or not self.external_key:
            raise UserError(_('Select a conversation to begin.'))
        if (customer.branch_id != self.branch_id or customer.company_id != self.company_id
                or account.branch_id != self.branch_id or account.company_id != self.company_id):
            raise AccessError(_('The selected company or branch is not allowed.'))
        return customer, account, session

    def _customer_link_preview(self, customer, account):
        identity = self.env['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', '=', self.channel_id.id), ('external_key', '=', self.external_key),
        ], limit=1)
        identity._authorize('read')
        previous = self.customer_id | identity.customer_id
        previous._authorize('read')
        phone = self._verified_sender_phone()
        matches = self._matching_saved_contacts(phone)
        manager = self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_crm_core.group_manager')
        if not manager and (matches - customer or previous - customer):
            raise AccessError(_('Only CRM managers can review ambiguous or conflicting customer links.'))
        snapshot = {
            'verified_phone': phone, 'matching_customer_ids': matches.ids,
            'customer_phone': customer._directory_data()['phone'],
            'customer_phones': customer._directory_data()['phones'],
            'customer_write_date': str(customer.write_date),
            'requires_confirmation': False,

            'conversation_id': self.id, 'account_id': account.id,
            'identity_id': identity.id, 'identity_active': identity.active,
            'external_key': self.external_key,
            'previous_customer_id': self.customer_id.id,
            'previous_identity_customer_id': identity.customer_id.id,
            'customer_id': customer.id, 'company_id': self.company_id.id,
            'branch_id': self.branch_id.id,
        }
        return identity, dict(snapshot,
            automatic_match=bool(phone and matches == customer and not previous - customer
                                 and (not identity or identity.active)),
            conflict=bool(previous - customer),
            fingerprint=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest())

    def action_preview_customer_link(self, customer_id):
        customer, account, session = self._customer_link_scope(customer_id)
        return self._customer_link_preview(customer, account)[1]

    def action_confirm_customer_link(self, customer_id, fingerprint, reason='', resolve_conflict=False, customer_confirmed=False):
        customer, account, session = self._customer_link_scope(customer_id)
        self.branch_id.lock_for_update()
        self.branch_id.sudo().write({})
        account.lock_for_update()
        customer.lock_for_update()
        self.lock_for_update()
        self.invalidate_recordset()
        customer.invalidate_recordset()
        account.invalidate_recordset()
        customer, account, session = self._customer_link_scope(customer_id)
        identity, preview = self._customer_link_preview(customer, account)
        automatic = preview['automatic_match'] and isinstance(reason, str) and not reason.strip()
        if automatic:
            reason = 'Automatically linked by unique verified phone match'
        reason = reason.strip()[:2000] if isinstance(reason, str) else ''
        reason = reason or 'Linked to existing customer'
        identity.lock_for_update()
        if preview['fingerprint'] != fingerprint:
            raise UserError(_('The customer link changed. Preview it again.'))
        if preview['conflict'] and resolve_conflict is not True:
            raise UserError(_('Explicitly resolve the conflicting customer link.'))
        flag = _WORKSPACE.set(True)
        try:
            if identity:
                identity.write({'customer_id': customer.id, 'active': True})
            else:
                identity = self.env['ab_crm_identity'].create({
                    'channel_id': self.channel_id.id, 'external_key': self.external_key,
                    'customer_id': customer.id, 'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id,
                })
            self.write({'customer_id': customer.id})
        finally:
            _WORKSPACE.reset(flag)
        self.env['ab_crm_workspace_audit'].sudo().create({
            'conversation_id': self.id, 'customer_id': customer.id,
            'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
            'user_id': self.env.uid, 'employee_id': session.employee_id.id,
            'action': 'auto_link_customer' if automatic else 'review_customer_link',
            'values': dict(preview, reason=reason.strip(), identity_id=identity.id,
                           association='verified_phone_match' if automatic else 'manual_review', customer_confirmed=customer_confirmed is True, phone_verified=bool(preview['verified_phone'] and customer in self._matching_saved_contacts(preview['verified_phone']))),
        })
        return {'customer_id': customer.id, 'conversation_id': self.id}

    def _customer_unlink_data(self, customer_id):
        customer, account, session = self._customer_link_scope(customer_id)
        if self.customer_id != customer:
            raise UserError(_('The customer link changed. Preview it again.'))
        streams = self._workspace_streams().sorted('id')
        if len(streams) < 2:
            raise UserError(_('Select a customer with linked conversations.'))
        for stream in streams:
            stream._customer_link_scope(customer_id)
        keys = {(stream.channel_id.id, stream.external_key) for stream in streams}
        identities = self.env['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', 'in', streams.channel_id.ids),
            ('external_key', 'in', streams.mapped('external_key')),
            ('company_id', '=', self.company_id.id), ('branch_id', '=', self.branch_id.id),
        ]).filtered(lambda identity: (identity.channel_id.id, identity.external_key) in keys).sorted('id')
        identities._authorize()
        if identities.filtered(lambda identity: identity.customer_id != customer):
            raise UserError(_('The customer link changed. Preview it again.'))
        snapshot = {
            'customer_id': customer.id, 'customer_write_date': str(customer.write_date),
            'conversations': [(stream.id, stream.customer_id.id, stream.messaging_account_id.id,
                               stream.external_key, str(stream.write_date)) for stream in streams],
            'identities': [(identity.id, identity.customer_id.id, identity.active,
                            str(identity.write_date)) for identity in identities],
        }
        preview = {'customer_id': customer.id, 'conversation_ids': streams.ids,
                   'fingerprint': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()}
        return customer, streams, identities, session, preview

    def action_preview_customer_unlink(self, customer_id):
        return self._customer_unlink_data(customer_id)[4]

    def action_unlink_customer(self, customer_id, fingerprint):
        customer, streams, identities, session, preview = self._customer_unlink_data(customer_id)
        self.branch_id.lock_for_update()
        self.branch_id.sudo().write({})
        streams.messaging_account_id.sorted('id').lock_for_update()
        customer.lock_for_update()
        streams.lock_for_update()
        identities.lock_for_update()
        streams.invalidate_recordset()
        identities.invalidate_recordset()
        customer.invalidate_recordset()
        customer, streams, identities, session, preview = self._customer_unlink_data(customer_id)
        if preview['fingerprint'] != fingerprint:
            raise UserError(_('The customer link changed. Preview it again.'))
        token = _WORKSPACE.set(True)
        try:
            identity_keys = {(identity.channel_id.id, identity.external_key) for identity in identities}
            values = [{'customer_id': customer.id, 'channel_id': stream.channel_id.id,
                       'external_key': stream.external_key, 'branch_id': stream.branch_id.id,
                       'company_id': stream.company_id.id, 'active': False}
                      for stream in streams if (stream.channel_id.id, stream.external_key) not in identity_keys]
            if values:
                self.env['ab_crm_identity'].create(values)
            identities.write({'active': False})
            streams.write({'customer_id': False})
        finally:
            _WORKSPACE.reset(token)
        self.env['ab_crm_workspace_audit'].sudo().create([
            {'conversation_id': stream.id, 'customer_id': customer.id,
             'branch_id': stream.branch_id.id, 'company_id': stream.company_id.id,
             'user_id': self.env.uid, 'employee_id': session.employee_id.id,
             'action': 'unlink_customer',
             'values': dict(preview, old_customer_id=customer.id, new_customer_id=False)}
            for stream in streams])
        return {'customer_id': customer.id, 'conversation_ids': streams.ids}

    def _auto_link_matching_customer(self):
        self.ensure_one()
        self._staff_action()
        self._authorize()
        self._workspace_scope()
        if (self.customer_id or not self.active or not self.channel_id.active
                or not self.messaging_account_id.active
                or self.channel_id.provider not in ('telegram', 'whatsapp')):
            return False
        phone = self._verified_sender_phone()
        matches = self._matching_saved_contacts(phone)
        if len(matches) != 1:
            return False
        self._customer_link_scope(matches.id)
        self.branch_id.lock_for_update()
        self.branch_id.sudo().write({})
        self.invalidate_recordset()
        matches.invalidate_recordset()
        matches.with_context(active_test=False).phone_ids.invalidate_recordset()
        if self.customer_id:
            return False
        phone = self._verified_sender_phone()
        matches = self._matching_saved_contacts(phone)
        if len(matches) != 1:
            return False
        customer, account, session = self._customer_link_scope(matches.id)
        identities = self.env['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', '=', self.channel_id.id), ('external_key', '=', self.external_key),
        ])
        identities.invalidate_recordset()
        if identities and (not identities.active or identities.customer_id != customer):
            return False
        preview = self._customer_link_preview(customer, account)[1]
        if not preview['automatic_match']:
            return False
        return self.action_confirm_customer_link(customer.id, preview['fingerprint'])

    def _auto_link_workspace_conversations(self):
        conversations = self.search(self._workspace_inbox_domain('') + [
            ('customer_id', '=', False), ('channel_id.active', '=', True),
            ('channel_id.provider', 'in', ('telegram', 'whatsapp')),
        ], order='branch_id, id')
        for conversation in conversations:
            try:
                conversation._workspace_scope()
                conversation._authorize()
            except (AccessError, UserError):
                continue
            if conversation.messaging_account_id:
                conversation._auto_link_matching_customer()

    def _verified_sender_phone(self):
        if self.channel_id.provider == 'whatsapp':
            inbound = self.env['ab_crm_messaging_event'].search_count([
                ('account_id', '=', self.messaging_account_id.id),
                ('message_id.conversation_id', '=', self.id),
            ], limit=1)
            phone = '+' + self.external_key if inbound else ''
        else:
            evidence = self.contact_evidence_id
            phone = evidence.telegram_phone if evidence.telegram_contact_owned else ''
        return normalized_phone(phone, self.company_id.country_id.code) or ''

    def _matching_saved_contacts(self, phone):
        if not phone:
            return self.env['ab_crm_customer']
        contacts = self.env['ab_crm_customer'].search([
            ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
        ])
        return contacts.filtered(lambda customer: phone in customer._active_phone_numbers())

    def action_customer_link_candidates(self):
        self.ensure_one()
        self._staff_action()
        self._authorize('read')
        self._workspace_scope()
        self._auto_link_matching_customer()
        phone = self._verified_sender_phone()
        return {'phone': phone, 'display_phone': display_phone(phone, self.company_id.country_id.code), 'contacts': [customer._directory_data()
                for customer in self._matching_saved_contacts(phone)]}

    @api.model
    def workspace_customer_inbox(self, query='', offset=0, limit=50):
        session = self._workspace_actor()
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
            raise ValidationError(_('Invalid conversation search.'))
        self._auto_link_workspace_conversations()
        domain = self._workspace_inbox_domain(query) + [('channel_id.active', '=', True)]
        accounts = self.env['ab_crm_messaging_account'].search([
            ('company_id', '=', session.company_id.id),
            ('branch_id', 'in', self.env['ab_crm_chatter_api']._directory_branches(session).ids),
        ])
        domain.append(('channel_id', 'in', accounts.channel_id.ids))
        groups = self._read_group(domain, ['customer_group_key'], ['id:max'],
                                  order='id:max DESC', offset=offset, limit=limit + 1)
        keys = [key for key, newest in groups[:limit]]
        conversations = self.search(self._workspace_inbox_domain('') + [('customer_group_key', 'in', keys),
                                    ('channel_id', 'in', accounts.channel_id.ids), ('channel_id.active', '=', True)])
        authorized = self.browse()
        for conversation in conversations:
            try:
                conversation._workspace_scope()
            except (AccessError, UserError):
                continue
            authorized |= conversation
        rows = {row['id']: row for row in authorized._workspace_inbox_rows(session)}
        items = []
        for key in keys:
            streams = authorized.filtered(lambda r: r.customer_group_key == key)
            if not streams:
                continue
            latest = streams.sorted(lambda r: (max(r.message_ids.mapped('timeline_at'), default=r.create_date), r.id))[-1]
            items.append(dict(rows[latest.id], group_key=key,
                streams=[dict(rows[r.id], account_id=r.messaging_account_id.id,
                              label=r.messaging_account_id.name) for r in streams],
                channels=sorted(set(streams.channel_id.mapped('provider'))),
                unread=sum(rows[r.id]['unread'] for r in streams)))
        return {'items': items, 'has_more': len(groups) > limit, 'next_offset': offset + limit}

    def workspace_detail(self, *args, **kwargs):
        self._auto_link_matching_customer()
        result = super().workspace_detail(*args, **kwargs)
        result['display_phone'] = display_phone(result['phone'] or self._verified_sender_phone(), self.company_id.country_id.code)
        result['link_suggestions'] = [contact._directory_data() for contact in
            self._matching_saved_contacts(self._verified_sender_phone())] if not self.customer_id else []
        return result

    def _workspace_orders(self, streams, stores):
        return self.env['ab_crm_channel_order'].search([
            ('conversation_id', 'in', streams.ids),
            ('company_id', '=', self.company_id.id), ('branch_id', '=', self.branch_id.id),
            '|', ('store_id', '=', False), ('store_id', 'in', stores.ids),
        ], order='id desc')
