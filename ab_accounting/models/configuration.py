from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Scope(models.AbstractModel):
    _name = 'ab_accounting_scope'
    _description = 'Accounting scope controls'

    def _manager(self):
        return self.env.user.has_group('ab_accounting.group_ab_accounting_manager') or self.env.user.has_group('base.group_system')

    def _bypass(self):
        return self._manager() or self.env.user.has_group('ab_accounting.group_ab_accounting_auto_je')

    def _require_manager(self):
        if not self._manager():
            raise AccessError(_('Only accounting managers can change configuration.'))

    def _require_poster(self):
        if not (self._bypass() or self.env.user.has_group('ab_accounting.group_ab_accounting_accountant')):
            raise AccessError(_('Journal creation and posting require Accountant or Auto JE access.'))

    def _check_scope(self, company, branch=None):
        if company not in self.env.user.company_ids or company.id not in self.env.context.get('allowed_company_ids', [self.env.user.company_id.id]):
            raise AccessError(_('The accounting company is not authorized.'))
        if branch:
            if not branch.active:
                raise ValidationError(_('The selected store must be active.'))
            if not self._bypass() and branch not in self.env.user.accounting_branch_ids:
                raise AccessError(_('You are not assigned to this accounting branch.'))

    def _serialize_stores(self, stores):
        """Coordinate accounting mutations without a separate branch registry.

        The no-op tuple update is intentional: a row lock alone would permit an
        old REPEATABLE READ snapshot after a competing journal/period commits.
        Updating the tuple makes Odoo retry that complete transaction. No store
        values, audit fields, company mapping or shared model schema are changed.
        """
        if not stores:
            return
        stores.check_access('read')
        stores.flush_recordset()
        self.env.cr.execute('SELECT id FROM ab_store WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(stores.ids)])
        self.env.cr.execute('UPDATE ab_store SET id = id WHERE id IN %s', [tuple(stores.ids)])
        stores.invalidate_recordset()



class Configuration(models.AbstractModel):
    _name = 'ab_accounting_configuration'
    _inherit = 'ab_accounting_scope'
    _description = 'Accounting configuration controls'

    @api.model_create_multi
    def create(self, vals_list):
        self._require_manager()
        records = super().create(vals_list)
        for rec in records:
            if 'company_id' in rec._fields:
                rec._check_scope(rec.company_id)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        self._require_manager()
        original_companies = {rec.id: rec.company_id.id for rec in self if 'company_id' in rec._fields}
        for rec in self:
            if 'company_id' in rec._fields:
                rec._check_scope(rec.company_id)
                if 'company_id' in vals and vals['company_id'] != rec.company_id.id:
                    raise UserError(_('An accounting configuration company cannot be changed.'))
        result = super().write(vals)
        for rec in self:
            if rec.id in original_companies and rec.company_id.id != original_companies[rec.id]:
                raise UserError(_('An accounting configuration company cannot be changed.'))
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        self._require_manager()
        self.env.registry.clear_cache()
        return super().unlink()


class Account(models.Model):
    _name = 'ab_accounting_account_guide'
    _inherit = 'ab_accounting_configuration'
    _description = 'Account'
    _parent_store = True
    _order = 'code, id'
    _rec_names_search = ['name', 'code']
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    parent_id = fields.Many2one('ab_accounting_account_guide', ondelete='restrict', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('ab_accounting_account_guide', 'parent_id')
    active = fields.Boolean(default=True)
    is_final = fields.Boolean(string='Posting Account', default=True)
    internal_group = fields.Selection([('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'), ('income', 'Income'), ('expense', 'Expense'), ('off_balance', 'Off Balance')], required=True, default='asset')
    internal_type = fields.Selection([('other', 'Other'), ('cash', 'Cash'), ('bank', 'Bank'), ('payable', 'Payable'), ('receivable', 'Receivable'), ('fixed_asset', 'Fixed Asset')], default='other', required=True)
    has_costcenter = fields.Boolean(string='Require Cost Center')
    has_partner = fields.Boolean(string='Require Partner')
    has_due_date = fields.Boolean(string='Require Due Date')
    costcenter_ids = fields.Many2many('ab_costcenter', string='Allowed Cost Centers')
    note = fields.Text()
    linked_account_id = fields.Many2one('ab_accounting_account', string='Account Classification', ondelete='restrict')
    _code_unique = models.Constraint('UNIQUE(company_id, code)', 'Account codes must be unique within a company.')

    @api.constrains('parent_id', 'company_id', 'is_final', 'linked_account_id')
    def _check_parent(self):
        if self._has_cycle():
            raise ValidationError(_('The account hierarchy cannot contain cycles.'))
        for rec in self:
            if rec.parent_id and (rec.parent_id.company_id != rec.company_id or rec.parent_id.is_final):
                raise ValidationError(_('A parent must be a group account in the same company.'))
            if rec.linked_account_id and rec.linked_account_id.company_id != rec.company_id:
                raise ValidationError(_('Classification must use a group account in the same company.'))
            if rec.is_final and rec.child_ids:
                raise ValidationError(_('An account with children cannot be a posting account.'))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.code, rec.name)


class DocType(models.Model):
    _name = 'ab_accounting_doctype'
    _inherit = 'ab_accounting_configuration'
    _description = 'Document Type'
    name = fields.Char(required=True, translate=True)
    internal_type = fields.Selection([('other', 'Other'), ('cash', 'Cash'), ('bank', 'Bank'), ('payable', 'Payable'), ('receivable', 'Receivable'), ('fixed_asset', 'Fixed Asset')], default='other')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)


class AuthGroup(models.Model):
    _name = 'ab_accounting_auth_group'
    _inherit = 'ab_accounting_configuration'
    _description = 'Accounting Authorization Profile'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    account_auth_ids = fields.One2many('ab_accounting_account_auth', 'group_id', copy=True)
    doctype_ids = fields.Many2many('ab_accounting_doctype')
    user_ids = fields.One2many('res.users', 'accounting_auth_group_id')

    @api.constrains('doctype_ids', 'company_id')
    def _check_documents(self):
        for rec in self:
            if any(d.company_id != rec.company_id for d in rec.doctype_ids):
                raise ValidationError(_('Authorization dimensions must belong to the same company.'))


class AccountAuth(models.Model):
    _name = 'ab_accounting_account_auth'
    _inherit = 'ab_accounting_configuration'
    _description = 'Account Authorization'
    _rec_name = 'account_id'
    group_id = fields.Many2one('ab_accounting_auth_group', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='group_id.company_id', store=True)
    account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict')
    own_account = fields.Boolean()
    allow_account = fields.Boolean()
    prevent_enquiry = fields.Boolean()
    always_show_account = fields.Boolean()
    _unique = models.Constraint('UNIQUE(group_id, account_id)', 'An account can occur once per authorization profile.')

    @api.constrains('account_id', 'group_id')
    def _check_company(self):
        for rec in self:
            if rec.account_id.company_id != rec.company_id:
                raise ValidationError(_('Authorization dimensions must belong to the same company.'))


class Users(models.Model):
    _inherit = 'res.users'
    accounting_branch_ids = fields.Many2many('ab_store', string='Accounting Branches')
    accounting_auth_group_id = fields.Many2one('ab_accounting_auth_group', string='Accounting Authorization Profile')
    responsible_for_ids = fields.Many2many('res.users', 'ab_accounting_reviewer_user_rel', 'reviewer_id', 'creator_id', string='Accounting Reviewer Responsibilities')

    def _accounting_bypass(self):
        self.ensure_one()
        return any(self.has_group('ab_accounting.' + g) for g in ['group_ab_accounting_manager', 'group_ab_accounting_auto_je']) or self.has_group('base.group_system')

    def _accounting_accounts(self, purpose='read'):
        self.ensure_one()
        auth = self.accounting_auth_group_id.account_auth_ids
        if purpose == 'always':
            selected = auth.filtered(lambda a: a.always_show_account and not a.prevent_enquiry)
        else:
            selected = auth.filtered(
                lambda a: (a.own_account or a.allow_account or (purpose == 'read' and a.always_show_account))
                and not (purpose == 'read' and a.prevent_enquiry)
            )
        denied = auth.filtered('prevent_enquiry') if purpose != 'post' else auth.browse()
        domain = fields.Domain('id', 'child_of', selected.account_id.ids)
        if denied:
            domain &= ~fields.Domain('id', 'child_of', denied.account_id.ids)
        return self.env['ab_accounting_account_guide'].with_context(active_test=False).search(domain).ids

    def _accounting_scope_domain(self, branch_field='branch_id'):
        domain = fields.Domain('company_id', 'in', list(set(self.company_ids.ids) & set(self.env.context.get('allowed_company_ids', [self.company_id.id]))))
        if not self._accounting_bypass():
            domain &= fields.Domain(branch_field, 'in', self.accounting_branch_ids.ids)
        return domain

    def _accounting_header_domain(self):
        domain = fields.Domain(self._accounting_scope_domain())
        if not self._accounting_bypass():
            domain &= fields.Domain('doctype_id', 'in', self.accounting_auth_group_id.doctype_ids.ids)
            allowed = self._accounting_accounts()
            domain &= fields.Domain('account_id', '=', False) | fields.Domain('account_id', 'in', allowed)
            domain &= ~fields.Domain('line_ids', 'any!', [('account_id', 'not in', allowed)])
            creator = fields.Domain('create_uid', 'in', [self.id] + self.responsible_for_ids.ids)
            always = self._accounting_accounts('always')
            shared = fields.Domain('line_ids', '!=', False)
            shared &= ~fields.Domain('line_ids', 'any!', [('account_id', 'not in', always)])
            shared &= fields.Domain('account_id', '=', False) | fields.Domain('account_id', 'in', always)
            domain &= creator | shared
        return domain

    def _accounting_line_domain(self):
        return fields.Domain('header_id', 'any!', self._accounting_header_domain())

    def _accounting_opening_line_domain(self):
        return fields.Domain('run_id', 'any!', self._accounting_opening_domain())

    def _accounting_opening_domain(self):
        domain = fields.Domain(self._accounting_scope_domain())
        if not self._accounting_bypass():
            domain &= ~fields.Domain('expected_ids', 'any!', [('account_id', 'not in', self._accounting_accounts())])
            domain &= ~fields.Domain('journal_ids', 'any!', ~self._accounting_header_domain())
        return domain

    @api.model_create_multi
    def create(self, vals_list):
        self._check_accounting_assignment(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_accounting_assignment([vals])
        result = super().write(vals)
        if {'accounting_branch_ids', 'accounting_auth_group_id', 'responsible_for_ids', 'company_ids'} & vals.keys():
            self.env.registry.clear_cache()
        return result

    def _check_accounting_assignment(self, vals_list):
        if any({'accounting_branch_ids', 'accounting_auth_group_id', 'responsible_for_ids'} & v.keys() for v in vals_list):
            self.env['ab_accounting_scope']._require_manager()


class Period(models.Model):
    _name = 'ab_accounting_period'
    _inherit = ['ab_accounting_configuration', 'mail.thread']
    _description = 'Accounting Period'
    _order = 'date_from desc, id'
    name = fields.Char(required=True)
    branch_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='open', required=True, readonly=True, tracking=True)
    reopen_reason = fields.Char(copy=False)
    reopened_by = fields.Many2one('res.users', readonly=True)
    reopened_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get('state', 'open') != 'open' or {'reopened_by', 'reopened_at'} & v.keys() for v in vals_list):
            raise UserError(_('Use the period workflow to change its state.'))
        for vals in vals_list:
            vals.update(state='open', reopened_by=False, reopened_at=False)
        self._serialize_stores(self.env['ab_store'].browse(sorted({v.get('branch_id', self.env.context.get('default_branch_id')) for v in vals_list} - {None, False})))
        return super().create(vals_list)

    def write(self, vals):
        if {'state', 'reopened_by', 'reopened_at'} & vals.keys():
            raise UserError(_('Use the period workflow to change its state.'))
        if {'branch_id', 'date_from', 'date_to'} & vals.keys():
            raise UserError(_('Period scope and dates are immutable; create the correct period instead.'))
        self._serialize_stores(self.branch_id)
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Accounting periods cannot be deleted.'))

    @api.constrains('company_id', 'branch_id', 'date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to or self.search_count(fields.Domain('company_id', '=', rec.company_id.id) & fields.Domain('branch_id', '=', rec.branch_id.id) & fields.Domain('id', '!=', rec.id) & fields.Domain('date_from', '<=', rec.date_to) & fields.Domain('date_to', '>=', rec.date_from)):
                raise ValidationError(_('Accounting periods must have valid, non-overlapping dates.'))

    def action_close(self):
        self._require_manager()
        self.check_access('write')
        self._serialize_stores(self.branch_id)
        return super(Period, self).write({'state': 'closed'})

    def action_reopen(self):
        self._require_manager()
        self.check_access('write')
        self._serialize_stores(self.branch_id)
        for rec in self:
            if rec.state != 'closed' or not (rec.reopen_reason or '').strip():
                raise ValidationError(_('Reopening a closed period requires a reason.'))
            rec.message_post(body=_('Period reopened: %s', rec.reopen_reason))
        return super(Period, self).write({'state': 'open', 'reopened_by': self.env.uid, 'reopened_at': fields.Datetime.now()})


class AccountFirstLevel(models.Model):
    _name = 'ab_accounting_account_first_level'
    _inherit = 'ab_accounting_configuration'
    _description = 'Account First Level'
    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    internal_group = fields.Selection([('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'), ('income', 'Income'), ('expense', 'Expense'), ('off_balance', 'Off Balance')], required=True)


class AccountSecondLevel(models.Model):
    _name = 'ab_accounting_account_second_level'
    _inherit = 'ab_accounting_configuration'
    _description = 'Account Second Level'
    name = fields.Char(required=True, translate=True)
    account_first_level_id = fields.Many2one('ab_accounting_account_first_level', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='account_first_level_id.company_id', store=True)


class AccountClassification(models.Model):
    _name = 'ab_accounting_account'
    _inherit = 'ab_accounting_configuration'
    _description = 'Account Classification'
    name = fields.Char(required=True, translate=True)
    account_second_level_id = fields.Many2one('ab_accounting_account_second_level', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='account_second_level_id.company_id', store=True)
    account_first_level_id = fields.Many2one(related='account_second_level_id.account_first_level_id')
    internal_group = fields.Selection(related='account_first_level_id.internal_group')
