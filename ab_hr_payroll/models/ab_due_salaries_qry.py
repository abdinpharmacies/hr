from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DueSalariesReport(models.Model):
    _name = 'ab_due_salaries_qry'
    _description = 'DueSalariesReport'
    _auto = False

    account_id = fields.Many2one('ab_accounting_account_guide')
    costcenter_id = fields.Many2one('ab_costcenter')
    costcenter_code = fields.Char()
    balance = fields.Float()
    due_salary_details_html = fields.Html(compute='_compute_due_salaries_details_html')
    redirected_to_ids = fields.Many2many('res.users', compute='_compute_redirected_to_ids')
    internal_working_employee = fields.Boolean(compute='_compute_internal_working_employee')
    show_only_cash = fields.Boolean(compute='_compute_show_only_cash', search='_search_show_only_cash')

    @api.depends('costcenter_id')
    def _compute_internal_working_employee(self):
        for rec in self:
            employees = self.env['ab_hr_employee'].sudo().search([
                ('costcenter_id', '=', rec.costcenter_id.id)])

            rec.internal_working_employee = any(employees.mapped('internal_working_employee'))

    def _compute_due_salaries_details_html(self):
        for rec in self:
            data = self._get_due_salaries_details_html(rec)
            html = self.env['ir.qweb']._render('ab_accounting.template_due_salaries_details_html', data)
            rec.due_salary_details_html = html

    def _get_due_salaries_details_html(self, rec):
        je = self.env['ab_accounting_je_line_qry'].sudo()
        headers = [_('Account'), _('Value'), _('Explain')]
        rows = []
        due_salaries_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries').id
        firing_parent_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_firing_parent').id

        last_due_salary = je.search([('costcenter_id', '=', rec.costcenter_id.id),
                                     ('account_id', '=', due_salaries_account_id),
                                     ('net_val', '<', -1),
                                     ], order='id desc', limit=1)

        account_id = last_due_salary.account_id.name
        value = round(last_due_salary.net_val, 2) * -1
        explain = (last_due_salary.explain or "") + " - Last Due Salary From HR"
        rows.append((account_id, value, explain))

        deductions = je.read_group(
            domain=[('costcenter_id', '=', rec.costcenter_id.id),
                    ('account_id.parent_id', '=', firing_parent_account_id)],
            fields=['costcenter_id', 'account_id', 'total_deduction:sum(net_val)'],
            groupby=['costcenter_id', 'account_id'],
            lazy=False
        )
        for deduction in deductions:
            account_id = self.env['ab_accounting_account_guide'].browse(deduction['account_id'][0]).name
            value = round(deduction['total_deduction'], 2) * -1
            explain = _("Future Deduction")
            rows.append((account_id, value, explain))

        return {
            'headers': headers,
            'rows': rows
        }

    def _compute_redirected_to_ids(self):
        for rec in self:
            rec.redirected_to_ids = self.env['ab_due_salaries_payment_redirect_to'].sudo().search(
                [('costcenter_id', '=', rec.costcenter_id.id)]).mapped('user_id')

    def init(self):
        due_salaries_account_id = 267
        firing_parent_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_firing_parent').id

        try:
            due_salaries_cash = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries_cash').id
        except:
            due_salaries_cash = due_salaries_account_id
        self._cr.execute(f"""
        DROP VIEW IF EXISTS {self._table} CASCADE ;
        ----------------------------------------------------
        CREATE OR REPLACE VIEW {self._table} AS
        SELECT min(je.id) as id, je.costcenter_id,je.account_id, costcenter_code,sum(je.net_val)*-1 as balance 
        FROM ab_accounting_je_line_qry je
        JOIN ab_accounting_je_header he on he.id = je.header_id
            WHERE je.account_id in (%s,%s) 
            AND je.active=True 
            AND he.is_posted = True 
        GROUP BY je.costcenter_id,je.costcenter_code,je.account_id
        HAVING abs(sum(je.net_val))>1
        """, (due_salaries_account_id, due_salaries_cash,))

    def _compute_show_only_cash(self):
        for rec in self:
            has_group_manager = self.env.user.has_group('ab_accounting.group_ab_accounting_manager')
            rec.show_only_cash = not has_group_manager

    def _search_show_only_cash(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        # self.env.cr.execute(" #### ")
        # ids = self.search([
        #     ('costcenter_id', 'in', self.env.user.costcenter_ids.ids),
        #     ('balance', '>', 0),
        #     ('account_id', '=', self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries_cash').id),
        # ]).ids
        #
        # if operator != '=':  # that means it is '!='
        #     val = not val
        return [
            ('costcenter_id', 'in', self.env.user.costcenter_ids.ids),
            ('balance', '>', 0),
            ('account_id', '=', self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries_cash').id),
        ]
