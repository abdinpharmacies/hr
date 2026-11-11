from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .workspace import _WORKSPACE, display_phone, normalized_phone


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    is_ab_customer = fields.Boolean(string='Is POS customer', compute='_compute_is_ab_customer')

    @api.depends('catalog_customer_id')
    def _compute_is_ab_customer(self):
        for contact in self:
            contact.is_ab_customer = bool(contact.catalog_customer_id)

    def _directory_data(self):
        return dict(super()._directory_data(), is_ab_customer=self.is_ab_customer,
                    catalog_customer_id=self.catalog_customer_id.id)


class PosHandoff(models.Model):
    _name = 'ab_crm_pos_handoff'
    _description = 'CRM POS Handoff'

    contact_id = fields.Many2one('ab_crm_customer', required=True, ondelete='restrict')
    session_id = fields.Many2one('ab_crm_chatter_session', required=True, ondelete='restrict')
    user_id = fields.Many2one(related='session_id.user_id', store=True)
    employee_id = fields.Many2one(related='session_id.employee_id', store=True)
    company_id = fields.Many2one(related='session_id.company_id', store=True)
    branch_id = fields.Many2one(related='contact_id.branch_id', store=True)
    conversation_id = fields.Many2one('ab_crm_conversation', ondelete='restrict')
    message_id = fields.Many2one('ab_crm_message', ondelete='restrict')
    phone_id = fields.Many2one('ab_crm_contact_phone', ondelete='restrict')
    draft_token = fields.Char(copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get():
            raise AccessError(_('Use Create order in Inbox.'))
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get():
            raise AccessError(_('Use Create order in Inbox.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('CRM handoffs cannot be deleted.'))


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    def _pos_contact(self, session, contact_id):
        if type(contact_id) is not int or contact_id <= 0:
            raise AccessError(_('Select a saved contact.'))
        contact = self.env['ab_crm_customer'].browse(contact_id).exists()
        if not contact or not contact.active:
            raise AccessError(_('Select a saved contact.'))
        contact._authorize()
        self._branch_scope(session, contact.branch_id)
        return contact

    def _pos_customer(self, customer_id):
        if type(customer_id) is not int or customer_id <= 0:
            raise AccessError(_('Select an active POS customer.'))
        customer = self.env['ab_customer'].browse(customer_id).exists()
        customer.check_access('read')
        if not customer or not customer.active:
            raise AccessError(_('Select an active POS customer.'))
        return customer

    def _link_pos_customer(self, session, contact, customer):
        contact.lock_for_update()
        contact.invalidate_recordset(['catalog_customer_id'])
        if contact.catalog_customer_id != customer:
            previous = contact._directory_data()
            guard = _WORKSPACE.set(True)
            try:
                contact.write({'catalog_customer_id': customer.id})
            finally:
                _WORKSPACE.reset(guard)
            self._contact_audit(session, contact, 'pos_customer_selected', previous)
        return contact._directory_data()

    @api.model
    def contact_pos_search(self, token, query='', branch_id=False, lookup=False, store_id=False):
        session = self._session(token)
        if not isinstance(query, str) or len(query) > 200:
            raise ValidationError(_('Invalid contact search.'))
        branch = self._branch_scope(session, self.env['ab_crm_branch'].browse(branch_id).exists())
        stores = branch.replica_id.allowed_sales_store_ids.filtered(lambda store: store.active and store.allow_sale)
        if session.profile_id.pos_allowed_store_ids:
            stores &= session.profile_id.pos_allowed_store_ids
        for store in stores:
            store.check_access('read')
        result = {'customers': [], 'stores': [{'id': store.id, 'name': store.name} for store in stores]}
        if not query.strip():
            return result
        phone = display_phone(normalized_phone(query, session.company_id.country_id.code), session.company_id.country_id.code)
        domain = [('active', '=', True), '|', ('customer_search', 'ilike', query.strip()),
                  ('customer_search', 'ilike', phone or query.strip())]
        customers = self.env['ab_customer'].search(domain, limit=30)
        if customers or not lookup:
            result['customers'] = [self.env['ab_sales_pos_api']._customer_payload(c) for c in customers]
            return result
        store = stores.filtered(lambda record: record.id == store_id) if store_id else branch.intake_store_id & stores
        if store_id and not store:
            raise AccessError(_('The selected company or branch is not allowed.'))
        if not store and len(stores) == 1:
            store = stores
        response = self.env['ab_sales_pos_api'].pos_customer_lookup(phone=phone, store_id=store.id)
        customer = response.get('customer')
        if customer:
            self._pos_customer(customer['id'])
        return dict(result, customers=[customer] if customer else [], message=response.get('message', ''))

    @api.model
    def contact_pos_select(self, token, customer_id, branch_id=False, contact_id=False):
        session = self._session(token)
        customer = self._pos_customer(customer_id)
        if contact_id:
            contact = self._pos_contact(session, contact_id)
        else:
            branch = self._branch_scope(session, self.env['ab_crm_branch'].browse(branch_id).exists())
            contact = self.env['ab_crm_customer'].search([
                ('branch_id', '=', branch.id), ('company_id', '=', session.company_id.id),
                ('catalog_customer_id', '=', customer.id),
            ], limit=1)
            if not contact:
                contact = self.contact_save(token, {
                    'name': customer.name or '',
                    'phone': customer.mobile_phone or customer.work_phone or '',
                    'address': customer.address or '',
                }, branch_id=branch.id)
                contact = self.env['ab_crm_customer'].browse(contact['id'])
        return self._link_pos_customer(session, contact, customer)

    @api.model
    def pos_handoff_start(self, token, contact_id, conversation_id=False, message_id=False, phone_id=False):
        session = self._session(token)
        contact = self._pos_contact(session, contact_id)
        conversation = self.env['ab_crm_conversation'].browse(conversation_id).exists()
        if conversation_id:
            conversation.with_context(ab_chatter_session_token=token)._workspace_scope()
            if (conversation.customer_id and conversation.customer_id != contact) or conversation.branch_id != contact.branch_id:
                raise AccessError(_('Select a conversation for this contact.'))
        message = self.env['ab_crm_message'].browse(message_id).exists()
        if message_id:
            message._authorize('read')
            if not conversation or message.conversation_id != conversation or message.direction != 'in' or not message._location_data():
                raise AccessError(_('Select an incoming location from this conversation.'))
        phone = self.env['ab_crm_contact_phone'].browse(phone_id).exists()
        if phone_id and (not phone or not phone.active or phone.customer_id != contact):
            raise AccessError(_('Select an active number on this contact.'))
        session.lock_for_update()
        session.write({})
        values = {'session_id': session.id, 'contact_id': contact.id,
                  'conversation_id': conversation.id, 'message_id': message.id, 'phone_id': phone.id}
        handoff = self.env['ab_crm_pos_handoff'].search(list((key, '=', value) for key, value in values.items()) + [('draft_token', '=', False)], limit=1)
        if not handoff:
            guard = _WORKSPACE.set(True)
            try:
                handoff = self.env['ab_crm_pos_handoff'].sudo().create(values)
            finally:
                _WORKSPACE.reset(guard)
        return handoff.id

    def _handoff_scope(self, token, handoff_id, pos_token, store_id=False):
        session = self._session(token)
        handoff = self.env['ab_crm_pos_handoff'].browse(handoff_id).exists()
        handoff.check_access('read')
        if not handoff or handoff.employee_id != session.employee_id or handoff.company_id != session.company_id:
            raise AccessError(_('Sign in with the employee who opened Create order.'))
        contact = self._pos_contact(session, handoff.contact_id.id)
        if handoff.conversation_id:
            handoff.conversation_id.with_context(ab_chatter_session_token=token)._workspace_scope()
            if (handoff.conversation_id.customer_id and handoff.conversation_id.customer_id != contact) or handoff.conversation_id.branch_id != contact.branch_id:
                raise AccessError(_('Select a conversation for this contact.'))
        pos = self.env['ab_sales_pos_api']._require_pos_operation_session(pos_token, store_id=store_id)
        if pos.employee_id != session.employee_id or pos.service_user_id != self.env.user:
            raise AccessError(_('Sign in with the employee who opened Create order.'))
        target = self.env['ab_store'].browse(store_id or pos.store_id.id)
        if store_id and target not in contact.branch_id.replica_id.allowed_sales_store_ids:
            raise AccessError(_('The selected company or branch is not allowed.'))
        return session, handoff, contact, target

    @api.model
    def pos_handoff_prepare(self, token, handoff_id, pos_token, store_id=False):
        session, handoff, contact, store = self._handoff_scope(token, handoff_id, pos_token, store_id)
        data = contact._directory_data()
        if contact.catalog_customer_id:
            self._pos_customer(contact.catalog_customer_id.id)
        phone = handoff.phone_id
        if phone and (not phone.active or phone.customer_id != contact):
            raise AccessError(_('Select an active number on this contact.'))
        data['phone'] = display_phone(phone.number if phone else data['phone'], session.company_id.country_id.code)
        if handoff.message_id:
            handoff.message_id._authorize('read')
            location = handoff.message_id._location_data()
            if not location or handoff.message_id.conversation_id != handoff.conversation_id:
                raise AccessError(_('Select an incoming location from this conversation.'))
            data['address'] = location.get('address') or location.get('name') or f"{location['latitude']}, {location['longitude']}"
        draft = self.env['ab_sales_pos_draft_cache'].sudo().search([
            ('pos_client_token', '=', handoff.draft_token), ('user_id', '=', self.env.uid),
            ('employee_id', '=', session.employee_id.id),
        ], limit=1) if handoff.draft_token else self.env['ab_sales_pos_draft_cache']
        return dict(data, draft_token=handoff.draft_token, draft_state=draft.state,
                    conversation_id=handoff.conversation_id.id)

    @api.model
    def pos_handoff_claim(self, token, handoff_id, pos_token, draft_token, store_id):
        if not isinstance(draft_token, str) or not 1 <= len(draft_token) <= 128:
            raise ValidationError(_('Invalid POS draft.'))
        session, handoff, contact, store = self._handoff_scope(token, handoff_id, pos_token, store_id)
        handoff.lock_for_update()
        handoff.invalidate_recordset(['draft_token'])
        if handoff.draft_token and handoff.draft_token != draft_token:
            raise AccessError(_('This contact handoff already has a POS draft.'))
        guard = _WORKSPACE.set(True)
        try:
            handoff.sudo().write({'draft_token': draft_token})
        finally:
            _WORKSPACE.reset(guard)
        return True

    @api.model
    def pos_handoff_sync(self, token, handoff_id, pos_token, draft_token):
        if not isinstance(draft_token, str) or not 1 <= len(draft_token) <= 128:
            raise ValidationError(_('Invalid POS draft.'))
        session, handoff, contact, store = self._handoff_scope(token, handoff_id, pos_token)
        draft = self.env['ab_sales_pos_draft_cache'].sudo().search([
            ('pos_client_token', '=', draft_token), ('user_id', '=', self.env.uid),
            ('employee_id', '=', session.employee_id.id),
        ], limit=1)
        if not draft or draft.store_id not in contact.branch_id.replica_id.allowed_sales_store_ids:
            raise AccessError(_('Invalid POS draft.'))
        self._handoff_scope(token, handoff_id, pos_token, draft.store_id.id)
        data = draft.bill_json or {}
        if data.get('crm_handoff_id') != handoff.id:
            raise AccessError(_('Invalid POS draft.'))
        handoff.lock_for_update()
        if handoff.draft_token and handoff.draft_token != draft_token:
            raise AccessError(_('This contact handoff already has a POS draft.'))
        guard = _WORKSPACE.set(True)
        try:
            handoff.sudo().write({'draft_token': draft_token})
        finally:
            _WORKSPACE.reset(guard)
        customer_id = (data.get('header') or {}).get('customer_id')
        invoice = self.env['ab_sales_header'].search([
            ('pos_client_token', '=', draft_token), ('create_uid', '=', self.env.uid),
        ], limit=1)
        if invoice:
            if invoice.store_id != draft.store_id or invoice.pos_hr_employee_id != session.employee_id:
                raise AccessError(_('Invalid POS draft.'))
            customer_id = invoice.customer_id.id or customer_id
        if customer_id:
            return self._link_pos_customer(session, contact, self._pos_customer(customer_id))
        return contact._directory_data()
