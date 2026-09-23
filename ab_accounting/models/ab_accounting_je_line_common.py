from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class JELineCommon(models.AbstractModel):
    _name = 'ab_accounting_je_line_common'
    _description = 'ab_accounting_je_line_common'

    credit_val = fields.Float(default=0, required=True, digits=(16, 2))
    debit_val = fields.Float(default=0, required=True, digits=(16, 2))
    store_id = fields.Many2one('ab_store',
                               domain=lambda self: [('id', 'not in', self.env.user.store_ids.ids)],
                               index=True,
                               ondelete='restrict')
    due_date = fields.Date(default=lambda self: self._context.get('date', fields.Date.context_today(self)),
                           index=True)

    costcenter_id = fields.Many2one('ab_costcenter', index=True, ondelete='restrict')
    doc_no = fields.Char(default='0', index=True)
    explain = fields.Text()

    account_id = fields.Many2one('ab_accounting_account_guide',
                                 index=True,
                                 domain=[
                                     '|',
                                     ('own_account', '=', True),
                                     ('allow_account', '=', True)
                                 ],
                                 auto_join=True,
                                 ondelete='restrict')

    is_confirmed = fields.Boolean(readonly=True, default=False, index=True)
    active = fields.Boolean(default=True, index=True)
    settlement_date = fields.Date(index=True)

    costcenter_space_sep = fields.Char(search='_search_costcenter_space_sep', compute='_compute_costcenter_space_sep', )
    doc_no_space_sep = fields.Char(search='_search_doc_no_space_sep', compute='_compute_doc_no_space_sep', )

    account_child_id = fields.Many2one('ab_accounting_account_guide',
                                       compute='_compute_account_child_id',
                                       search='_search_account_child_id',
                                       string='Account(s)',
                                       compute_sudo=True)

    def _compute_account_child_id(self):
        for rec in self:
            rec.account_child_id = rec.account_id.id

    def _search_account_child_id(self, operator, val):
        acc_guide_mo = self.env['ab_accounting_account_guide'].with_context(active_test=False)
        if operator == '=':
            accounts_ids = acc_guide_mo.search([('id', '=', val)]).ids
        elif operator == 'ilike' and '%' not in val:
            # search for exact search_term
            accounts_ids = list(acc_guide_mo._name_search(name=val, operator='=ilike', limit=1000))
            # if exact search_term not available, then expand search_term
            if not accounts_ids:
                accounts_ids = list(acc_guide_mo._name_search(name=val, operator=operator, limit=1000))
        else:
            accounts_ids = list(acc_guide_mo._name_search(name=val, operator=operator, limit=1000))

        domains = [[('account_id', 'child_of', account_id)] for account_id in accounts_ids]
        domain = expression.OR(domains) if domains else [(0, '=', 1)]

        return domain

    @api.constrains('doc_no')
    def constrains_je_line_doc_no(self):
        for rec in self:
            if not rec.doc_no:
                raise ValidationError(_("You must enter code"))
            elif ' ' in rec.doc_no:
                raise ValidationError(_("Code must not have spaces"))

    def _compute_costcenter_space_sep(self):
        for rec in self:
            rec.costcenter_space_sep = rec.costcenter_id.id

    def _search_costcenter_space_sep(self, operator, value):
        if operator in ['in', 'ilike', 'not in', 'not ilike']:
            value = [v.strip() for v in value.split()]
            operator = 'in' if operator in ['in', 'ilike'] else 'not in'

        ids = self.sudo().search([('costcenter_id.code', operator, value)]).ids
        return [('id', 'in', ids)]

    def _compute_doc_no_space_sep(self):
        for rec in self:
            rec.doc_no_space_sep = rec.doc_no

    def _search_doc_no_space_sep(self, operator, value):
        if operator in ['in', 'ilike', 'not in', 'not ilike']:
            value = [v.strip() for v in value.split()]
            operator = 'in' if operator in ['in', 'ilike'] else 'not in'

        ids = self.sudo().search([('doc_no', operator, value)]).ids
        return [('id', 'in', ids)]
