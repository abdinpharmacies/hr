from contextvars import ContextVar
from .request_cache import cached_scope
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .workspace import normalized_phone, display_phone, _WORKSPACE


_DIRECTORY_GROUPS = 'ab_crm_sales_workspace.group_agent,ab_crm_core.group_manager,base.group_system'
_DIRECTORY_NORMALIZATION = ContextVar('ab_directory_normalization', default=False)
_DIRECTORY_KEYS = {'directory_name_key', 'directory_chatter_name_key',
                   'directory_phone_key', 'directory_legacy_phone'}


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    chatter_name = fields.Char(copy=False)
    chatter_phone = fields.Char(copy=False, index=True)
    chatter_address = fields.Text(copy=False)
    chatter_override = fields.Boolean(copy=False)

    directory_name_key = fields.Char(string='Name', compute='_compute_directory_keys', store=True, index='trigram', groups=_DIRECTORY_GROUPS)
    directory_chatter_name_key = fields.Char(string='Name', compute='_compute_directory_keys', store=True, index='trigram', groups=_DIRECTORY_GROUPS)
    directory_phone_key = fields.Text(string='Phone', compute='_compute_directory_keys', store=True, index='trigram', groups=_DIRECTORY_GROUPS)
    directory_legacy_phone = fields.Char(string='Phone', compute='_compute_directory_keys', store=True, index=True, groups=_DIRECTORY_GROUPS)

    @api.depends('name', 'chatter_name', 'phone', 'chatter_phone', 'chatter_override',
                 'phone_ids.number', 'phone_ids.active', 'company_id.partner_id.country_id.code')
    def _compute_directory_keys(self):
        token = _DIRECTORY_NORMALIZATION.set(True)
        try:
            for customer in self:
                customer.directory_name_key = (customer.name or '').casefold()
                customer.directory_chatter_name_key = (customer.chatter_name or '').casefold()
                numbers = customer._active_phone_numbers()
                tokens = set(numbers)
                tokens.update(''.join(filter(str.isdigit, number)) for number in numbers)
                tokens.update(''.join(filter(str.isdigit, display_phone(number, customer.company_id.country_id.code)))
                              for number in numbers)
                customer.directory_phone_key = '\n'.join(sorted(tokens))
                customer.directory_legacy_phone = numbers[0] if numbers and not customer.with_context(active_test=False).phone_ids else False
        finally:
            _DIRECTORY_NORMALIZATION.reset(token)

    @api.model
    def _backfill_directory_search(self, batch_size=1000):
        if not self.env.su or type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise AccessError(_('Invalid contact search.'))
        cursor = 0
        count = 0
        while True:
            batch = self.with_context(active_test=False).search([('id', '>', cursor)], order='id', limit=batch_size)
            if not batch:
                break
            names = sorted(_DIRECTORY_KEYS)
            for name in names:
                self.env.add_to_compute(self._fields[name], batch)
            batch._recompute_recordset(names)
            batch.flush_recordset(names)
            cursor = batch[-1].id
            count += len(batch)
            self.env.invalidate_all()
        self.env['ir.config_parameter'].sudo().set_param('ab_crm_sales_workspace.directory_search_ready', '1')
        return count

    @api.model
    def _directory_query_domain(self, query='', phone=False):
        domain = fields.Domain.TRUE
        if query:
            needle = query.casefold().strip()
            escaped = needle.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            pattern = '%' + escaped + '%'
            match = (fields.Domain('directory_name_key', '=like', pattern)
                     | fields.Domain('directory_chatter_name_key', '=like', pattern))
            digits = ''.join(filter(str.isdigit, query))
            if digits:
                match |= fields.Domain('directory_phone_key', '=like', '%' + digits + '%')
            canonical = normalized_phone(query, self.env.company.country_id.code)
            if canonical:
                match |= fields.Domain('phone_ids', 'any', [('active', '=', True), ('number', '=', canonical)])
                match |= fields.Domain('directory_legacy_phone', '=', canonical)
            domain &= match
        if phone:
            domain &= (fields.Domain('phone_ids', 'any', [('active', '=', True), ('number', '=', phone)])
                       | fields.Domain('directory_legacy_phone', '=', phone))
        return domain

    @api.model_create_multi
    def create(self, values_list):
        if not _DIRECTORY_NORMALIZATION.get() and (
                any(_DIRECTORY_KEYS.intersection(values) for values in values_list)
                or any('default_' + key in self.env.context for key in _DIRECTORY_KEYS)):
            raise AccessError(self.env._('Use Contacts in Sales Chatter to edit this contact.'))
        if not _WORKSPACE.get() and any(
            any(key.startswith('chatter_') for key in values) for values in values_list
        ):
            raise AccessError(_('Use Contacts in Sales Chatter to edit this contact.'))
        return super().create(values_list)

    def write(self, values):
        if _DIRECTORY_KEYS.intersection(values) and not _DIRECTORY_NORMALIZATION.get():
            raise AccessError(self.env._('Use Contacts in Sales Chatter to edit this contact.'))
        if not _WORKSPACE.get() and any(key.startswith('chatter_') for key in values):
            raise AccessError(_('Use Contacts in Sales Chatter to edit this contact.'))
        return super().write(values)

    def _directory_data(self):
        self.ensure_one()
        names = [self.chatter_name, self.name, self.catalog_customer_id.name]
        name = next((value for value in names if value and not value.replace('+', '').replace(' ', '').isdigit()), '')
        return {
            'id': self.id,
            'name': name or display_phone(normalized_phone(self.chatter_phone or self.phone, self.company_id.country_id.code), self.company_id.country_id.code) or _('Unidentified sender'),
            'phone': (self.chatter_phone if self.chatter_override else self.phone)
            or '',
            'address': (self.chatter_address if self.chatter_override else self.address)
            or '',
            'branch_id': self.branch_id.id,
        }

    def _matches_directory_query(self, query):
        self.ensure_one()
        needle = query.casefold().strip()
        digits = ''.join(filter(str.isdigit, query))
        canonical = normalized_phone(query, self.company_id.country_id.code)
        return any(needle in (value or '').casefold() for value in (self.name, self.chatter_name)) or any(
            canonical == number or (digits and (digits in number or digits in ''.join(filter(str.isdigit,
                display_phone(number, self.company_id.country_id.code))))) for number in self._active_phone_numbers())


class WorkspaceAudit(models.Model):
    _name = 'ab_crm_workspace_audit'
    _description = 'Protected Chatter Action Log'
    _order = 'id desc'

    conversation_id = fields.Many2one('ab_crm_conversation', ondelete='restrict')
    message_id = fields.Many2one('ab_crm_message', ondelete='restrict')
    customer_id = fields.Many2one('ab_crm_customer', ondelete='restrict')
    branch_id = fields.Many2one('ab_crm_branch', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, ondelete='restrict')
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    employee_id = fields.Many2one('ab_hr_employee', required=True, ondelete='restrict')
    action = fields.Char(required=True)
    at = fields.Datetime(default=fields.Datetime.now, required=True)
    values = fields.Json()

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.su:
            raise AccessError(_('Protected chatter logs cannot be changed.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Protected chatter logs cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Protected chatter logs cannot be changed.'))


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    @cached_scope
    def _branch_scope(self, session, branch):
        branch.ensure_one()
        branch.check_access('read')
        if not branch.active or branch.company_id != session.company_id:
            raise AccessError(_('The selected company or branch is not allowed.'))
        for user in self.env.user | session.employee_id.user_id:
            if (
                not (
                    user.has_group('base.group_system')
                    or user.has_group('ab_crm_core.group_manager')
                )
                and user not in branch.user_ids
            ):
                raise AccessError(_('The selected company or branch is not allowed.'))
        stores = branch.replica_id.allowed_sales_store_ids.filtered(
            lambda store: store.active and store.allow_sale
        )
        allowed = session.profile_id.pos_allowed_store_ids
        if not stores or (allowed and not stores & allowed):
            raise AccessError(_('The selected company or branch is not allowed.'))
        return branch

    @cached_scope
    def _directory_branches(self, session):
        branches = self.env['ab_crm_branch'].search(
            [('company_id', '=', session.company_id.id)]
        )
        result = branches.browse()
        for branch in branches:
            try:
                self._branch_scope(session, branch)
            except AccessError:
                continue
            result |= branch
        return result

    @api.model
    def contact_search(self, token, query='', offset=0, phone=False, branch_id=False):
        session = self._session(token)
        if (
            not isinstance(query, str)
            or len(query) > 200
            or type(offset) is not int
            or offset < 0
        ):
            raise ValidationError(_('Invalid contact search.'))
        branches = self._directory_branches(session)
        if branch_id:
            branches = self._branch_scope(
                session, self.env['ab_crm_branch'].browse(branch_id)
            )
        domain = [
            ('branch_id', 'in', branches.ids),
            ('company_id', '=', session.company_id.id),
        ]
        customer_model = self.env['ab_crm_customer']
        ready = self.env['ir.config_parameter'].sudo().get_param('ab_crm_sales_workspace.directory_search_ready') == '1'
        if phone:
            phone = normalized_phone(phone, session.company_id.country_id.code)
            if not phone:
                raise ValidationError(_('Enter a valid customer phone number.'))
        if ready:
            contacts = customer_model.search(
                fields.Domain(domain) & customer_model._directory_query_domain(query, phone),
                order='id desc', offset=offset, limit=31)
        elif not query and not phone:
            contacts = customer_model.search(domain, order='id desc', offset=offset, limit=31)
        else:
            contacts = customer_model.search(domain, order='id desc')
            if query:
                contacts = contacts.filtered(lambda contact: contact._matches_directory_query(query))
            if phone:
                contacts = contacts.filtered(lambda contact: phone in contact._active_phone_numbers())
            contacts = contacts[offset:offset + 31]
        return {
            'contacts': [contact._directory_data() for contact in contacts[:30]],
            'has_more': len(contacts) > 30,
            'branches': [{'id': branch.id, 'name': branch.name} for branch in branches],
        }

    @api.model
    def contact_save(self, token, values, contact_id=False, branch_id=False):
        session = self._session(token)
        if (
            not isinstance(values, dict)
            or set(values) != {'name', 'phone', 'address'}
            or any(not isinstance(value, str) for value in values.values())
        ):
            raise ValidationError(_('Enter a name, phone and address.'))
        name = values['name'].strip()
        phone = normalized_phone(values['phone'], session.company_id.country_id.code)
        if not name or len(name) > 200 or len(values['address']) > 2000:
            raise ValidationError(_('Enter a name, phone and address.'))
        if not phone:
            raise ValidationError(_('Enter a valid customer phone number.'))
        contact = (
            self.env['ab_crm_customer'].browse(contact_id).exists()
            if contact_id
            else self.env['ab_crm_customer']
        )
        if contact_id and not contact:
            raise AccessError(_('Select a saved contact.'))
        if contact:
            contact._authorize()
            self._branch_scope(session, contact.branch_id)
            contact.branch_id.lock_for_update()
            contact.branch_id.sudo().write({})
            contact.lock_for_update()
        else:
            branch = self._branch_scope(
                session, self.env['ab_crm_branch'].browse(branch_id).exists()
            )
            branch.lock_for_update()
            branch.sudo().write({})
        previous = contact._directory_data() if contact else {}
        if contact and ((contact.primary_phone_id and phone != contact.primary_phone_id.number)
                or (not contact.primary_phone_id and contact._active_phone_numbers() and phone not in contact._active_phone_numbers())):
            raise UserError(_('Use Add number or select another primary number.'))
        if not contact:
            existing = self.env['ab_crm_customer'].search([('branch_id', '=', branch.id), ('company_id', '=', session.company_id.id)])
            if existing.filtered(lambda c: phone in c._active_phone_numbers()) and not existing._manager():
                raise AccessError(_('Only CRM managers can resolve shared numbers.'))
        guard = _WORKSPACE.set(True)
        try:
            if contact:
                contact.write(
                    {
                        'chatter_name': name,
                        'chatter_phone': phone,
                        'chatter_address': values['address'].strip(),
                        'chatter_override': True,
                    }
                )
            else:
                contact = self.env['ab_crm_customer'].create(
                    {
                        'name': name,
                        'phone': phone,
                        'address': values['address'].strip(),
                        'branch_id': branch.id,
                        'company_id': session.company_id.id,
                    }
                )
        finally:
            _WORKSPACE.reset(guard)
        if not contact.primary_phone_id:
            contact._save_phone(phone, '', 'Saved contact phone', self.env.user)
        self._contact_audit(
            session,
            contact,
            'edit_contact' if contact_id else 'create_contact',
            previous,
        )
        return contact._directory_data()

    def _contact_audit(self, session, contact, action, previous):
        self.env['ab_crm_workspace_audit'].sudo().create(
            {
                'customer_id': contact.id,
                'branch_id': contact.branch_id.id,
                'company_id': session.company_id.id,
                'user_id': self.env.uid,
                'employee_id': session.employee_id.id,
                'action': action,
                'values': {'old': previous, 'new': contact._directory_data()},
            }
        )

    @api.model
    def contact_archive(self, token, contact_id):
        session = self._session(token)
        contact = self.env['ab_crm_customer'].browse(contact_id).exists()
        if not contact:
            raise AccessError(_('Select a saved contact.'))
        contact._authorize()
        self._branch_scope(session, contact.branch_id)
        contact.branch_id.lock_for_update()
        contact.branch_id.sudo().write({})
        contact.lock_for_update()
        previous = contact._directory_data()
        contact.write({'active': False})
        self._contact_audit(session, contact, 'archive_contact', previous)
        return True

    @api.model
    def contact_accounts(self, token, contact_id):
        session = self._session(token)
        contact = self.env['ab_crm_customer'].browse(contact_id).exists()
        if not contact:
            raise AccessError(_('Select a saved contact.'))
        contact._authorize('read')
        self._branch_scope(session, contact.branch_id)
        streams = self.env['ab_crm_conversation'].search([
            ('customer_id', '=', contact.id), ('branch_id', '=', contact.branch_id.id),
            ('company_id', '=', session.company_id.id),
        ])
        accounts = []
        for stream in streams:
            try:
                stream.with_context(ab_chatter_session_token=token)._workspace_scope()
            except (AccessError, UserError):
                continue
            accounts.append({'id': stream.id, 'provider': stream.channel_id.provider,
                'display_destination': stream._display_destination(), 'label': stream.messaging_account_id.name})
        return {'accounts': accounts}

    @api.model
    def contact_open(self, token, contact_id):
        session = self._session(token)
        contact = self.env['ab_crm_customer'].browse(contact_id).exists()
        contact._authorize('read')
        self._branch_scope(session, contact.branch_id)
        conversation = self.env['ab_crm_conversation'].search(
            [
                ('customer_id', '=', contact.id),
                ('branch_id', '=', contact.branch_id.id),
                ('company_id', '=', session.company_id.id),
            ],
            limit=1,
            order='id desc',
        )
        return {
            'conversation_id': conversation.id,
            'contact': contact._directory_data(),
        }
