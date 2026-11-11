import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .workspace import _WORKSPACE, normalized_phone, display_phone


class ContactPhone(models.Model):
    _name = 'ab_crm_contact_phone'
    _inherit = 'ab_crm_scoped'
    _description = 'Contact Phone'
    _rec_name = 'number'
    _order = 'id'

    customer_id = fields.Many2one('ab_crm_customer', required=True, ondelete='restrict', check_company=True)
    number = fields.Char(required=True, index=True)
    label = fields.Char()
    active = fields.Boolean(default=True)
    customer_confirmed = fields.Boolean(readonly=True)
    reason = fields.Text(required=True, readonly=True)
    actor_id = fields.Many2one('res.users', required=True, readonly=True)
    confirmed_at = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)

    _number_unique = models.Constraint('UNIQUE(customer_id, number)', 'This number is already saved on this contact.')

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get():
            raise AccessError(_('Use the reviewed contact phone actions.'))
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get():
            raise AccessError(_('Use the reviewed contact phone actions.'))
        return super().write(values)

    @api.constrains('customer_id', 'number', 'branch_id', 'company_id')
    def _check_contact_phone(self):
        for record in self:
            if (record.customer_id.branch_id != record.branch_id
                    or record.customer_id.company_id != record.company_id
                    or normalized_phone(record.number, record.company_id.country_id.code) != record.number):
                raise ValidationError(_('Select a valid number in the contact scope.'))


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    phone_ids = fields.One2many('ab_crm_contact_phone', 'customer_id')
    primary_phone_id = fields.Many2one('ab_crm_contact_phone', ondelete='restrict', copy=False)
    canonical_customer_id = fields.Many2one('ab_crm_customer', ondelete='restrict', copy=False, readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        protected = {'phone_ids', 'primary_phone_id', 'canonical_customer_id'}
        if not _WORKSPACE.get() and (any(set(v) & protected for v in values_list)
                or any('default_' + field in self.env.context for field in protected)):
            raise AccessError(_('Use the reviewed contact phone actions.'))
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get() and set(values) & {'phone_ids', 'primary_phone_id', 'canonical_customer_id'}:
            raise AccessError(_('Use the reviewed contact phone actions.'))
        return super().write(values)

    @api.constrains('primary_phone_id', 'canonical_customer_id')
    def _check_phone_owner(self):
        for record in self:
            if record.primary_phone_id and (record.primary_phone_id.customer_id != record or not record.primary_phone_id.active):
                raise ValidationError(_('Select an active number on this contact.'))
            canonical = record.canonical_customer_id
            if canonical and (canonical == record or canonical.canonical_customer_id
                    or canonical.branch_id != record.branch_id or canonical.company_id != record.company_id):
                raise ValidationError(_('Select an authorized matching customer.'))

    def _active_phone_numbers(self):
        self.ensure_one()
        if self.with_context(active_test=False).phone_ids:
            return self.phone_ids.filtered('active').mapped('number')
        return list(filter(None, [normalized_phone(
            self.chatter_phone if self.chatter_override else self.phone, self.company_id.country_id.code)]))

    def _directory_data(self):
        result = super()._directory_data()
        phones = self.phone_ids.filtered('active')
        result['can_manage'] = self._manager()
        result['phones'] = [{'id': phone.id, 'number': phone.number, 'display_number': display_phone(phone.number, self.company_id.country_id.code), 'label': phone.label or '',
                             'primary': phone == self.primary_phone_id,
                             'customer_confirmed': phone.customer_confirmed} for phone in phones]
        if self.primary_phone_id:
            result['phone'] = self.primary_phone_id.number
        result['display_phone'] = display_phone(result['phone'], self.company_id.country_id.code)
        return result

    def _save_phone(self, number, label, reason, actor, confirmed=False, primary=False, active=True):
        self.ensure_one()
        phone = self.with_context(active_test=False).phone_ids.filtered(lambda p: p.number == number)
        guard = _WORKSPACE.set(True)
        try:
            values = {'label': label, 'reason': reason, 'actor_id': actor.id,
                      'customer_confirmed': confirmed, 'confirmed_at': fields.Datetime.now(), 'active': active}
            if phone:
                phone.write(values)
            else:
                phone = self.env['ab_crm_contact_phone'].create(dict(values, customer_id=self.id,
                    number=number, branch_id=self.branch_id.id, company_id=self.company_id.id))
            if primary or (active and not self.primary_phone_id):
                self.write({'primary_phone_id': phone.id, 'chatter_phone': number,
                            'chatter_override': True, 'chatter_address': self._directory_data()['address']})
        finally:
            _WORKSPACE.reset(guard)
        return phone


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    def _phone_contact_scope(self, token, contact_id, manager=False):
        session = self._session(token)
        contact = self.env['ab_crm_customer'].browse(contact_id).exists()
        if not contact or not contact.active or contact.canonical_customer_id:
            raise AccessError(_('Select a saved contact.'))
        contact._staff_action()
        contact._authorize()
        self._branch_scope(session, contact.branch_id)
        if manager and not contact._manager():
            raise AccessError(_('Only CRM managers can review contact matches.'))
        contact.branch_id.lock_for_update()
        contact.branch_id.sudo().write({})
        contact.lock_for_update()
        contact.invalidate_recordset()
        if not contact.active or contact.canonical_customer_id:
            raise AccessError(_('Select a saved contact.'))
        return session, contact

    def _phone_reason(self, reason):
        if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 2000:
            raise ValidationError(_('Enter a customer link review reason.'))
        return reason.strip()

    def _phone_conflicts(self, contact, number):
        contacts = self.env['ab_crm_customer'].search([
            ('branch_id', '=', contact.branch_id.id), ('company_id', '=', contact.company_id.id),
            ('id', '!=', contact.id)])
        return contacts.filtered(lambda c: number in c._active_phone_numbers())

    @api.model
    def contact_phone_add(self, token, contact_id, number, label='', reason='', customer_confirmed=False, resolve_shared=False):
        session, contact = self._phone_contact_scope(token, contact_id)
        reason = self._phone_reason(reason)
        number = normalized_phone(number, session.company_id.country_id.code)
        if not number or not isinstance(label, str) or len(label) > 100:
            raise ValidationError(_('Enter a valid customer phone number.'))
        if customer_confirmed is not True:
            raise UserError(_('Confirm that this number belongs to the same customer.'))
        if self._phone_conflicts(contact, number) and not (contact._manager() and resolve_shared is True):
            raise AccessError(_('Only CRM managers can resolve shared numbers.'))
        previous = contact._directory_data()
        if not contact.with_context(active_test=False).phone_ids:
            legacy = contact._active_phone_numbers()
            if legacy:
                contact._save_phone(legacy[0], '', 'Existing effective contact phone', self.env.user)
        contact._save_phone(number, label.strip(), reason, self.env.user, confirmed=True)
        self._contact_audit(session, contact, 'add_contact_phone', dict(previous, reason=reason))
        return contact._directory_data()

    @api.model
    def contact_phone_update(self, token, contact_id, phone_id, action, reason, label=''):
        session, contact = self._phone_contact_scope(token, contact_id)
        reason = self._phone_reason(reason)
        phone = contact.phone_ids.filtered(lambda p: p.id == phone_id and p.active)
        if not phone or action not in ('primary', 'archive', 'label') or not isinstance(label, str) or len(label) > 100:
            raise AccessError(_('Select an active number on this contact.'))
        if action == 'archive' and phone == contact.primary_phone_id:
            raise UserError(_('Select another primary number before archiving this number.'))
        previous = contact._directory_data()
        guard = _WORKSPACE.set(True)
        try:
            if action == 'primary':
                contact.write({'primary_phone_id': phone.id, 'chatter_phone': phone.number})
            elif action == 'archive':
                phone.write({'active': False})
            else:
                phone.write({'label': label.strip()})
        finally:
            _WORKSPACE.reset(guard)
        self._contact_audit(session, contact, 'contact_phone_' + action, dict(previous, reason=reason))
        return contact._directory_data()

    @api.model
    def contact_initialize_phones(self, token, contact_id):
        session, contact = self._phone_contact_scope(token, contact_id, manager=True)
        previous = contact._directory_data()
        if not contact.with_context(active_test=False).phone_ids:
            effective = contact._active_phone_numbers()
            if effective:
                contact._save_phone(effective[0], '', 'Existing effective contact phone', self.env.user)
            legacy = normalized_phone(contact.phone, contact.company_id.country_id.code)
            if legacy and legacy not in effective:
                contact._save_phone(legacy, '', 'Different legacy phone requires review', self.env.user, active=False)
            self._contact_audit(session, contact, 'initialize_contact_phones', previous)
        review_numbers = contact.with_context(active_test=False).phone_ids.filtered(lambda p: not p.active).mapped('number')
        return dict(contact._directory_data(), review_numbers=review_numbers,
            review_display_numbers=[display_phone(number, contact.company_id.country_id.code) for number in review_numbers])

    def _consolidation_preview(self, canonical, duplicate, token):
        identities = self.env['ab_crm_identity'].with_context(active_test=False).search([('customer_id', 'in', (canonical | duplicate).ids)])
        streams = self.env['ab_crm_conversation'].with_context(active_test=False).search([('customer_id', 'in', (canonical | duplicate).ids)])
        for stream in streams:
            stream.with_context(ab_chatter_session_token=token)._workspace_scope()
        snapshot = {'canonical': canonical._directory_data(), 'duplicate': duplicate._directory_data(),
                    'identities': [(r.id, r.customer_id.id, r.active, str(r.write_date)) for r in identities],
                    'conversations': [(r.id, r.customer_id.id, str(r.write_date)) for r in streams],
                    'identity_details': [{'id': r.id, 'customer_id': r.customer_id.id, 'provider': r.channel_id.provider, 'account': r.external_key, 'display_account': display_phone('+' + r.external_key.lstrip('+'), r.company_id.country_id.code) if r.channel_id.provider == 'whatsapp' and r.external_key.lstrip('+').isdigit() else r.external_key, 'active': r.active} for r in identities],
                    'conversation_details': [{'id': r.id, 'customer_id': r.customer_id.id, 'provider': r.channel_id.provider, 'destination': r._display_destination(), 'label': r.messaging_account_id.name} for r in streams]}
        return dict(snapshot, fingerprint=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest())

    @api.model
    def contact_consolidate(self, token, canonical_id, duplicate_id, fingerprint=False, reason=''):
        session, canonical = self._phone_contact_scope(token, canonical_id, manager=True)
        duplicate = self.env['ab_crm_customer'].browse(duplicate_id).exists()
        duplicate._authorize('read')
        if not duplicate or duplicate.branch_id != canonical.branch_id or duplicate.company_id != canonical.company_id:
            raise AccessError(_('Select an authorized matching customer.'))
        session, duplicate = self._phone_contact_scope(token, duplicate_id, manager=True)
        if canonical == duplicate or canonical.branch_id != duplicate.branch_id or canonical.company_id != duplicate.company_id:
            raise AccessError(_('Select an authorized matching customer.'))
        preview = self._consolidation_preview(canonical, duplicate, token)
        if not fingerprint:
            return preview
        reason = self._phone_reason(reason)
        if fingerprint != preview['fingerprint']:
            raise UserError(_('The customer link changed. Preview it again.'))
        if not canonical.with_context(active_test=False).phone_ids:
            for number in canonical._active_phone_numbers():
                canonical._save_phone(number, '', 'Existing effective contact phone', self.env.user)
        for number in duplicate._active_phone_numbers():
            if number not in canonical._active_phone_numbers():
                canonical._save_phone(number, '', reason, self.env.user, confirmed=True)
        identities = self.env['ab_crm_identity'].with_context(active_test=False).search([('customer_id', '=', duplicate.id)])
        streams = self.env['ab_crm_conversation'].with_context(active_test=False).search([('customer_id', '=', duplicate.id)])
        for stream in streams:
            stream.with_context(ab_chatter_session_token=token)._workspace_scope()
        guard = _WORKSPACE.set(True)
        try:
            identities.write({'customer_id': canonical.id})
            streams.write({'customer_id': canonical.id})
            duplicate.write({'canonical_customer_id': canonical.id, 'active': False})
        finally:
            _WORKSPACE.reset(guard)
        self._contact_audit(session, canonical, 'consolidate_contacts', dict(preview, reason=reason))
        return canonical._directory_data()
