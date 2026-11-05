from contextvars import ContextVar
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_INTERNAL = ContextVar('ab_crm_internal', default=False)


class Scoped(models.AbstractModel):
    _name = 'ab_crm_scoped'
    _description = 'CRM Branch Scope'
    _check_company_auto = True

    branch_id = fields.Many2one('ab_crm_branch', required=True, ondelete='restrict', index=True, check_company=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)

    def _staff_action(self):
        if self.env.user.has_group('ab_crm_core.group_service'):
            raise AccessError(_('Integration service accounts cannot approve staff decisions.'))

    def _manager(self):
        return self.env.su or self.env.user.has_group('ab_crm_core.group_manager') or self.env.user.has_group('base.group_system')

    def _authorize(self, operation='write'):
        self.check_access(operation)
        for record in self:
            record.branch_id.check_access('read')
            if record.company_id not in self.env.companies or record.branch_id.company_id != record.company_id:
                raise AccessError(_('The selected company or branch is not allowed.'))
            if not self._manager() and self.env.user not in record.branch_id.user_ids:
                raise AccessError(_('The selected company or branch is not allowed.'))

    def _internal_write(self, values):
        token = _INTERNAL.set(True)
        try:
            return self.write(values)
        finally:
            _INTERNAL.reset(token)

    @api.model_create_multi
    def create(self, values_list):
        records = super().create(values_list)
        records._authorize('create')
        return records

    def write(self, values):
        self._authorize()
        if any(values.get(key, record[key].id) != record[key].id for record in self for key in ('branch_id', 'company_id')):
            raise AccessError(_('Branch and company cannot be changed after creation.'))
        result = super().write(values)
        self._authorize()
        return result

    def unlink(self):
        raise UserError(_('Archive records instead of deleting them.'))


class Branch(models.Model):
    _name = 'ab_crm_branch'
    _description = 'CRM Branch'
    _check_company_auto = True

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    user_ids = fields.Many2many('res.users', string='Authorized Staff', check_company=True)
    _code_unique = models.Constraint('UNIQUE(company_id, code)', 'Branch code must be unique per company.')

    def unlink(self):
        raise UserError(_('Archive records instead of deleting them.'))


class Channel(models.Model):
    _name = 'ab_crm_channel'
    _inherit = 'ab_crm_scoped'
    _description = 'CRM Channel'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    provider = fields.Selection([('phone', 'Phone'), ('whatsapp', 'WhatsApp'), ('telegram', 'Telegram'), ('website', 'Website')], required=True)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('UNIQUE(code)', 'Channel code must be unique.')


class Customer(models.Model):
    _name = 'ab_crm_customer'
    _inherit = 'ab_crm_scoped'
    _description = 'CRM Customer'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    phone = fields.Char(index=True)
    address = fields.Text()
    identity_ids = fields.One2many('ab_crm_identity', 'customer_id')

    def action_phone_candidates(self):
        self.ensure_one()
        self._authorize('read')
        return {'type': 'ir.actions.act_window', 'name': _('Customer Candidates'), 'res_model': self._name,
                'view_mode': 'list,form', 'domain': [('phone', '=', self.phone), ('id', '!=', self.id)]}


class Identity(models.Model):
    _name = 'ab_crm_identity'
    _inherit = 'ab_crm_scoped'
    _description = 'CRM Identity Link'
    _rec_name = 'external_key'

    customer_id = fields.Many2one('ab_crm_customer', required=True, ondelete='restrict', check_company=True)
    channel_id = fields.Many2one('ab_crm_channel', required=True, ondelete='restrict', check_company=True)
    external_key = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    _identity_unique = models.Constraint('UNIQUE(channel_id, external_key)', 'This identity is already linked.')

    @api.constrains('customer_id', 'channel_id', 'branch_id')
    def _check_scope(self):
        for record in self:
            for target in (record.customer_id, record.channel_id):
                target.check_access('read')
                if target.branch_id != record.branch_id:
                    raise ValidationError(_('Related records must belong to the same branch.'))


class Conversation(models.Model):
    _name = 'ab_crm_conversation'
    _inherit = 'ab_crm_scoped'
    _description = 'CRM Conversation'
    _order = 'write_date desc, id desc'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    channel_id = fields.Many2one('ab_crm_channel', required=True, ondelete='restrict', check_company=True)
    customer_id = fields.Many2one('ab_crm_customer', ondelete='restrict', check_company=True)
    external_key = fields.Char(index=True)
    assigned_id = fields.Many2one('res.users', string='Assigned Staff', readonly=True, copy=False)
    state = fields.Selection([('new', 'New'), ('progress', 'In Progress'), ('waiting', 'Waiting'), ('closed', 'Closed')], default='new', required=True)
    message_ids = fields.One2many('ab_crm_message', 'conversation_id')
    _thread_unique = models.Constraint('UNIQUE(channel_id, external_key)', 'This conversation already exists.')

    @api.constrains('channel_id', 'customer_id', 'branch_id')
    def _check_scope(self):
        for record in self:
            for target in (record.channel_id, record.customer_id):
                if target:
                    target.check_access('read')
                    if target.branch_id != record.branch_id:
                        raise ValidationError(_('Related records must belong to the same branch.'))

    @api.model_create_multi
    def create(self, values_list):
        if any(v.get('assigned_id') for v in values_list):
            raise AccessError(_('Use Claim to assign a conversation.'))
        for values in values_list:
            values['assigned_id'] = False
        return super().create(values_list)

    def write(self, values):
        if 'assigned_id' in values and not _INTERNAL.get():
            raise AccessError(_('Use Claim to assign a conversation.'))
        return super().write(values)

    def action_claim(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        for record in self:
            if record.assigned_id and record.assigned_id != self.env.user and not self._manager():
                raise UserError(_('This conversation is already assigned.'))
        return self._internal_write({'assigned_id': self.env.uid, 'state': 'progress'})


class Message(models.Model):
    _name = 'ab_crm_message'
    _inherit = 'ab_crm_scoped'
    _description = 'CRM Message'
    _order = 'id'
    _rec_name = 'body'

    conversation_id = fields.Many2one('ab_crm_conversation', required=True, ondelete='restrict', check_company=True)
    body = fields.Text(required=True)
    direction = fields.Selection([('note', 'Staff Note'), ('in', 'Incoming'), ('out', 'Outgoing')], default='note', required=True)
    delivery_state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'), ('unknown', 'Unknown'), ('sent', 'Sent'), ('failed', 'Failed')], default='draft', readonly=True, required=True)
    provider_event = fields.Char(readonly=True, index=True)
    provider_reference = fields.Char(readonly=True)
    token = fields.Char(default=lambda self: str(uuid4()), required=True, readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)
    _event_unique = models.Constraint('UNIQUE(provider_event)', 'This message was already received.')
    _token_unique = models.Constraint('UNIQUE(token)', 'Message token must be unique.')

    @api.constrains('conversation_id', 'branch_id')
    def _check_scope(self):
        for record in self:
            record.conversation_id.check_access('read')
            if record.conversation_id.branch_id != record.branch_id:
                raise ValidationError(_('Related records must belong to the same branch.'))

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get() and any(v.get('direction') == 'in' or any(k in v for k in ('delivery_state', 'provider_event', 'provider_reference', 'token', 'approved_by', 'approved_at')) for v in values_list):
            raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        if not _INTERNAL.get():
            for values in values_list:
                values.update(delivery_state='draft', provider_event=False, provider_reference=False, token=str(uuid4()), approved_by=False, approved_at=False)
                values.setdefault('direction', 'note')
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            if any(r.direction in ('note', 'in') or r.delivery_state != 'draft' for r in self):
                raise UserError(_('Append a new message or note instead of changing history.'))
            if set(values) - {'body'}:
                raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        return super().write(values)

    def action_approve(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        if any(r.direction != 'out' or r.delivery_state != 'draft' or not r.conversation_id.external_key for r in self):
            raise UserError(_('Only a draft reply with a destination can be approved.'))
        self._internal_write({'delivery_state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})
        return True
