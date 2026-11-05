from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .workspace import normalized_phone, _WORKSPACE


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    chatter_name = fields.Char(copy=False)
    chatter_phone = fields.Char(copy=False, index=True)
    chatter_address = fields.Text(copy=False)
    chatter_override = fields.Boolean(copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if not _WORKSPACE.get() and any(
            any(key.startswith('chatter_') for key in values) for values in values_list
        ):
            raise AccessError(_('Use Contacts in Sales Chatter to edit this contact.'))
        return super().create(values_list)

    def write(self, values):
        if not _WORKSPACE.get() and any(key.startswith('chatter_') for key in values):
            raise AccessError(_('Use Contacts in Sales Chatter to edit this contact.'))
        return super().write(values)

    def _directory_data(self):
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.chatter_name if self.chatter_override else self.name,
            'phone': (self.chatter_phone if self.chatter_override else self.phone)
            or '',
            'address': (self.chatter_address if self.chatter_override else self.address)
            or '',
            'branch_id': self.branch_id.id,
        }


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
        if query:
            domain += [
                '|',
                '|',
                '|',
                ('name', 'ilike', query),
                ('phone', 'ilike', query),
                ('chatter_name', 'ilike', query),
                ('chatter_phone', 'ilike', query),
            ]
        if phone:
            phone = normalized_phone(phone, session.company_id.country_id.code)
            if not phone:
                raise ValidationError(_('Enter a valid customer phone number.'))
            pattern = '%' + '%'.join(c for c in phone[-7:] if c.isdigit()) + '%'
            domain += [
                '|',
                ('phone', 'ilike', pattern),
                ('chatter_phone', 'ilike', pattern),
            ]
            contacts = self.env['ab_crm_customer'].search(domain, order='id desc')
            contacts = contacts.filtered(
                lambda contact: phone
                in (
                    normalized_phone(contact.phone, session.company_id.country_id.code),
                    normalized_phone(
                        contact.chatter_phone, session.company_id.country_id.code
                    ),
                )
            )[offset : offset + 31]
        else:
            contacts = self.env['ab_crm_customer'].search(
                domain, limit=31, offset=offset, order='id desc'
            )
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
            contact.lock_for_update()
        else:
            branch = self._branch_scope(
                session, self.env['ab_crm_branch'].browse(branch_id).exists()
            )
        previous = contact._directory_data() if contact else {}
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
        contact.lock_for_update()
        previous = contact._directory_data()
        contact.write({'active': False})
        self._contact_audit(session, contact, 'archive_contact', previous)
        return True

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
