from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountingReport(models.TransientModel):
    _name = 'ab_accounting_report'
    _inherit = 'ab_accounting_scope'
    _description = 'Accounting Report'
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    branch_id = fields.Many2one('ab_store', required=True)
    date_from = fields.Date(required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    report_type = fields.Selection([('ledger', 'General Ledger'), ('trial', 'Trial Balance'), ('statement', 'Account Statement'), ('opening', 'Opening Reconciliation')], required=True, default='trial')
    account_ids = fields.Many2many('ab_accounting_account_guide')
    partner_id = fields.Many2one('res.partner')
    costcenter_id = fields.Many2one('ab_costcenter')
    opening_run_id = fields.Many2one('ab_accounting_opening_run')

    @api.model
    def _secured_domain(self, company, branch, accounts=None, partner=None, costcenter=None):
        self._check_scope(company, branch)
        domain = fields.Domain('company_id', '=', company.id) & fields.Domain('branch_id', '=', branch.id) & fields.Domain('state', '=', 'posted')
        # Explicit ordinary-user domain even if a caller supplied sudo().
        domain &= fields.Domain('header_id', 'any', self.env.user._accounting_header_domain())
        if accounts:
            accounts.check_access('read')
            if any(a.company_id != company for a in accounts):
                raise ValidationError(_('Report accounts must belong to the selected company.'))
            domain &= fields.Domain('account_id', 'in', accounts.ids)
        if partner:
            partner.check_access('read')
            domain &= fields.Domain('partner_id', '=', partner.id)
        if costcenter:
            costcenter.check_access('read')
            domain &= fields.Domain('costcenter_id', '=', costcenter.id)
        return domain

    def get_report_data(self):
        self.ensure_one()
        self.check_access('read')
        domain = self._secured_domain(self.company_id, self.branch_id, self.account_ids, self.partner_id, self.costcenter_id)
        if self.date_from > self.date_to:
            raise ValidationError(_('The report start date must not follow its end date.'))
        if self.report_type == 'opening':
            run = self.opening_run_id
            if not run or run.company_id != self.company_id or run.branch_id != self.branch_id:
                raise ValidationError(_('Select an opening run in the report branch.'))
            rows = run.reconciliation()
            for row in rows:
                row['account'] = self.env['ab_accounting_account_guide'].browse(row['account_id']).display_name
                row['partner'] = self.env['res.partner'].browse(row['partner_id']).display_name if row['partner_id'] else ''
                row['costcenter'] = self.env['ab_costcenter'].browse(row['costcenter_id']).display_name if row['costcenter_id'] else ''
            if self.account_ids:
                rows = [r for r in rows if r['account_id'] in self.account_ids.ids]
            if self.partner_id:
                rows = [r for r in rows if r['partner_id'] == self.partner_id.id]
            if self.costcenter_id:
                rows = [r for r in rows if r['costcenter_id'] == self.costcenter_id.id]
            return {'columns': [_('Account'), _('Partner'), _('Cost Center'), _('Expected'), _('Posted Actual'), _('Difference')], 'rows': [[r[k] for k in ['account', 'partner', 'costcenter', 'expected', 'actual', 'difference']] for r in rows]}
        # The same secured dimension domain covers both carry-forward and movements.
        lines = self.env['ab_accounting_je_line'].search(domain & fields.Domain('accounting_date', '<=', self.date_to), order='accounting_date, posting_number, id')
        balances = defaultdict(lambda: [0.0, 0.0, 0.0])
        labels = {}
        movements = []
        for line in lines:
            key = (line.account_id.id, line.partner_id.id, line.costcenter_id.id)
            labels[key] = [line.account_id.display_name, line.partner_id.display_name or '', line.costcenter_id.display_name or '']
            if line.accounting_date < self.date_from:
                balances[key][0] += line.net_val
            else:
                balances[key][1] += line.debit_val
                balances[key][2] += line.credit_val
                movements.append((key, line))
        if self.report_type == 'trial':
            return {'columns': [_('Account'), _('Partner'), _('Cost Center'), _('Opening'), _('Debit'), _('Credit'), _('Closing')], 'rows': [labels[k] + balances[k] + [balances[k][0] + balances[k][1] - balances[k][2]] for k in sorted(balances)]}
        running = {k: values[0] for k, values in balances.items()}
        rows = [labels[k] + [str(self.date_from), '', _('Opening Balance'), 0.0, 0.0, running[k]] for k in sorted(balances)]
        for key, line in movements:
            running[key] += line.net_val
            rows.append(labels[key] + [str(line.accounting_date), line.posting_number, line.explain, line.debit_val, line.credit_val, running[key]])
        return {'columns': [_('Account'), _('Partner'), _('Cost Center'), _('Accounting Date'), _('Posting Number'), _('Description'), _('Debit'), _('Credit'), _('Running Balance')], 'rows': rows}

    def action_pdf(self):
        self.get_report_data()
        return self.env.ref('ab_accounting.action_report_pdf').report_action(self)

    def action_xlsx(self):
        self.get_report_data()
        return self.env.ref('ab_accounting.action_report_xlsx').report_action(self)

    def action_items(self):
        self.ensure_one()
        domain = self._secured_domain(self.company_id, self.branch_id, self.account_ids, self.partner_id, self.costcenter_id)
        domain &= fields.Domain('accounting_date', '>=', self.date_from) & fields.Domain('accounting_date', '<=', self.date_to)
        return {'type': 'ir.actions.act_window', 'name': _('Posted Journal Items'), 'res_model': 'ab_accounting_je_line', 'view_mode': 'list,pivot,form', 'domain': list(domain.map_conditions(lambda c: fields.Domain.TRUE if c.field_expr == 'header_id' else c)), 'context': {'create': False}}
