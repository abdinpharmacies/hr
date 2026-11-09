import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .workspace import _WORKSPACE


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
        return super().action_identify(phone, customer_id, confirmed)

    def _customer_link_scope(self, customer_id):
        self.ensure_one()
        self._staff_action()
        if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_crm_core.group_manager')):
            raise AccessError(_('Only CRM managers can review customer links.'))
        self._authorize()
        session, stores = self._workspace_scope()
        if type(customer_id) is not int or customer_id <= 0:
            raise AccessError(_('Select an authorized matching customer.'))
        customer = self.env['ab_crm_customer'].browse(customer_id).exists()
        customer._authorize('read')
        account = self.messaging_account_id
        account._authorize('read')
        if (not customer or not customer.active or not account or not self.active
                or customer.branch_id != self.branch_id or customer.company_id != self.company_id
                or account.branch_id != self.branch_id or account.company_id != self.company_id
                or not self.external_key):
            raise AccessError(_('Select an authorized matching customer.'))
        return customer, account, session

    def _customer_link_preview(self, customer, account):
        identity = self.env['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', '=', self.channel_id.id), ('external_key', '=', self.external_key),
        ], limit=1)
        identity._authorize('read')
        previous = self.customer_id | identity.customer_id
        previous._authorize('read')
        snapshot = {
            'conversation_id': self.id, 'account_id': account.id,
            'identity_id': identity.id, 'identity_active': identity.active,
            'external_key': self.external_key,
            'previous_customer_id': self.customer_id.id,
            'previous_identity_customer_id': identity.customer_id.id,
            'customer_id': customer.id, 'company_id': self.company_id.id,
            'branch_id': self.branch_id.id,
        }
        return identity, dict(snapshot,
            conflict=bool(previous - customer),
            fingerprint=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest())

    def action_preview_customer_link(self, customer_id):
        customer, account, session = self._customer_link_scope(customer_id)
        return self._customer_link_preview(customer, account)[1]

    def action_confirm_customer_link(self, customer_id, fingerprint, reason, resolve_conflict=False):
        customer, account, session = self._customer_link_scope(customer_id)
        if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 2000:
            raise ValidationError(_('Enter a customer link review reason.'))
        account.lock_for_update()
        self.lock_for_update()
        self.invalidate_recordset()
        identity, preview = self._customer_link_preview(customer, account)
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
            'action': 'review_customer_link',
            'values': dict(preview, reason=reason.strip(), identity_id=identity.id,
                           association='manual_review', phone_verified=False),
        })
        return {'customer_id': customer.id, 'conversation_id': self.id}

    @api.model
    def workspace_customer_inbox(self, query='', offset=0, limit=50):
        session = self._workspace_actor()
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
            raise ValidationError(_('Invalid conversation search.'))
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

    def _workspace_orders(self, streams, stores):
        return self.env['ab_crm_channel_order'].search([
            ('conversation_id', 'in', streams.ids),
            ('company_id', '=', self.company_id.id), ('branch_id', '=', self.branch_id.id),
            '|', ('store_id', '=', False), ('store_id', 'in', stores.ids),
        ], order='id desc')
