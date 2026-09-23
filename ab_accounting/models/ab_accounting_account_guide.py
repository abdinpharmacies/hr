# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AccGuide(models.Model):
    _name = 'ab_accounting_account_guide'
    _description = 'ab_accounting_account_guide'
    _order = 'code'

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    linked_account_id = fields.Many2one('ab_accounting_account', index=True, auto_join=True)

    name = fields.Char(required=True, index=True, translate=False)
    currency_id = fields.Many2one('res.currency', string='Account Currency',
                                  help="Forces all moves for this account to have this account currency.")
    code = fields.Char(size=64, index=True)
    include_initial_balance = fields.Boolean(string="Bring Accounts Balance Forward",
                                             help="Used in reports to know if we should consider journal items "
                                                  " from the beginning of time instead of from the fiscal year only. "
                                                  "Account types that should be reset to zero at each new fiscal year "
                                                  "(like expenses, revenue..) should not have this option set.")

    internal_type = fields.Selection([
        ('other', 'Other'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('payable', 'Payable'),
        ('receivable', 'Receivable'),
        ('fixed_asset', 'Fixed Asset'),
        ('fixed_asset_je', 'Fixed Asset JE'),
    ], required=True, default='other',
        help="The 'Internal Type' is used for features available on "
             "different types of accounts: cash bank accounts"
             ", payable/receivable is for vendor/customer accounts.")
    internal_group = fields.Selection([
        ('equity', 'Equity'),
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('off_balance', 'Off Balance'),

    ], string="Internal Group",
        required=True,
        help="The 'Internal Group' is used to filter accounts based on the internal group set on the account type.")

    nature = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit'),
        ('switch', 'Switch'),
    ], compute='_compute_nature')

    note = fields.Text(string='Description')

    reconcile = fields.Boolean(string='Allow Reconciliation', default=False,
                               help="Check this box if this account "
                                    "need manual reconcile.")

    calc_balance = fields.Boolean(default=True)
    has_costcenter = fields.Boolean(default=False, string='Balance on Costcenter')
    has_store = fields.Boolean(default=False, string='Balance on Store')

    has_due_date = fields.Boolean(default=True, help="Has Due Date Different Than Today's Date")

    parent_id = fields.Many2one('ab_accounting_account_guide',
                                string='Parent Account',
                                ondelete='restrict',
                                index=True)

    child_ids = fields.One2many(
        'ab_accounting_account_guide', 'parent_id',
        string='Child Accounts')

    children_ids = fields.Many2many(comodel_name='ab_accounting_account_guide',
                                    relation='ab_accounting_account_guide_children_rel',
                                    column1='parent_id',
                                    column2='child_id',
                                    compute='_compute_children_ids',
                                    search='_search_children_ids',
                                    string='Children of:')

    is_final = fields.Boolean(compute='_compute_is_final', search='_search_is_final')

    account_auth_ids = fields.One2many('ab_accounting_account_auth', inverse_name='account_id')
    max_negative_value = fields.Float(default=1)
    active = fields.Boolean(default=True)

    own_account = fields.Boolean(compute='_compute_auth_account',
                                 search='_search_own_account',
                                 compute_sudo=True)

    allow_account = fields.Boolean(compute='_compute_auth_account',
                                   search='_search_allow_account',
                                   compute_sudo=True)

    always_show_account = fields.Boolean(compute='_compute_auth_account',
                                         search='_search_always_show_account',
                                         compute_sudo=True)

    prevent_enquiry = fields.Boolean(compute='_compute_auth_account',
                                     search='_search_prevent_enquiry',
                                     compute_sudo=True)
    salary_deduction = fields.Boolean(default=False)

    costcenter_ids = fields.Many2many(
        comodel_name='ab_costcenter',
        relation='ab_accounting_account_guide_ab_costcenter_rel',
        column1='account_id',
        column2='costcenter_id',
        string='Allowed Costcenters',
        help="If this field is empty, then all costcenters allowed."
    )

    related_to = fields.Selection(
        selection=[('hq', 'HQ'),
                   ('branch', 'Branch'),
                   ], default='hq')

    def _compute_auth_account(self):
        own_account_ids = set(self._search_own_account('=', True)[0][2])
        allow_account_ids = set(self._search_allow_account('=', True)[0][2])
        prevent_enquiry_ids = set(self._search_prevent_enquiry('=', True)[0][2])
        always_show_account_ids = set(self._search_always_show_account('=', True)[0][2])
        for rec in self:
            rec.own_account = rec.id in own_account_ids
            rec.allow_account = rec.id in allow_account_ids
            rec.prevent_enquiry = rec.id in prevent_enquiry_ids
            rec.always_show_account = rec.id in always_show_account_ids

    def _search_own_account(self, operator, val):
        return self._search_auth_account(operator=operator, val=val, auth_type='own_account')

    def _search_allow_account(self, operator, val):
        return self._search_auth_account(operator=operator, val=val, auth_type='allow_account')

    def _search_always_show_account(self, operator, val):
        return self._search_auth_account(operator=operator, val=val, auth_type='always_show_account')

    def _search_prevent_enquiry(self, operator, val):
        return self._search_auth_account(operator=operator, val=val, auth_type='prevent_enquiry')

    def _search_auth_account(self, operator, val, auth_type=None):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = []
        parent_accounts = self.env.user.account_auth_ids.filtered(auth_type).mapped("account_id.id")
        if parent_accounts:
            ids = self.search([('id', 'child_of', parent_accounts), ('is_final', '=', True)]).ids
        if operator != '=':  # that means it is '!='
            val = not val

        return [('id', 'in' if val else 'not in', ids)]

    @api.depends('parent_id')
    def _compute_children_ids(self):
        for rec in self:
            rec.children_ids = self.search([('id', 'child_of', rec.id),
                                            ('is_final', '=', True)])

    def _search_children_ids(self, operator, val):
        accounts = self.search([('name', operator, val)])
        ids = []
        for account in accounts:
            ids += self.search([('id', 'child_of', account.id),
                                ('is_final', '=', True)]).ids

        return [('id', 'in', ids)]

    @api.depends('internal_group')
    def _compute_nature(self):
        for rec in self:
            if rec.internal_group in ('asset', 'expense'):
                rec.nature = 'debit'
            elif rec.internal_group in ('equity', 'liability', 'income'):
                rec.nature = 'credit'
            else:
                rec.nature = 'switch'

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise ValidationError('Error! You cannot create recursive categories.')

    @api.depends('parent_id', 'parent_path')
    def _compute_is_final(self):
        for rec in self:
            if rec.child_ids:
                rec.is_final = False
            else:
                rec.is_final = True

    def _search_is_final(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = self.search([('child_ids', '=', False)]).sudo().ids

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    def write(self, vals):
        res = super().write(vals)
        # allowed_fields = {'parent_path', 'name', 'code', 'note', 'reconcile',
        #                   'has_costcenter', 'has_store', 'has_due_date', 'nature',
        #                   'max_negative_value'}
        # je = self.env['ab_accounting_je_line'].sudo().search([('account_id', '=', self.id)], limit=1)
        #
        # if je and not set(vals).issubset(allowed_fields):
        #     raise UserError(_("You can not edit properties of this account because JE created"))

        return res

    _sql_constraints = [
        ('ab_accounting_account_guide_name_unique', 'unique(name)', 'NAME CAN NOT BE DUPLICATED.'),
        ('ab_accounting_account_guide_code_unique', 'check(1=1)', 'CODE CAN NOT BE DUPLICATED.'),
    ]

    def copy(self, default=None):
        default = default or {}
        default['name'] = self.name + ' copy'
        return super().copy(default=default)

    def name_get(self):
        res = []
        context = self.env.context.get('show_parent_account')
        for rec in self:
            if context:
                name_items = [rec.parent_id.name, rec.name]
                res.append((rec.id, ' / '.join(str(it) for it in name_items)))
            else:
                res.append((rec.id, rec.name))

        return res
