from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountingGuideAuthorization(models.Model):
    _inherit = 'ab_accounting_account_guide'

    account_auth_ids = fields.One2many(
        'ab_accounting_account_auth', inverse_name='account_id')
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
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        return self._search_auth_account(operator=operator, val=val, auth_type='own_account')

    def _search_allow_account(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        return self._search_auth_account(operator=operator, val=val, auth_type='allow_account')

    def _search_always_show_account(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        return self._search_auth_account(operator=operator, val=val, auth_type='always_show_account')

    def _search_prevent_enquiry(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
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
