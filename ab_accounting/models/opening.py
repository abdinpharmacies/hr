from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare
from .journal import amount


class OpeningRun(models.Model):
    _name = 'ab_accounting_opening_run'
    _inherit = ['ab_accounting_scope', 'mail.thread']
    _description = 'Opening Run'
    name = fields.Char(string='Reference', required=True)
    branch_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    accounting_date = fields.Date(required=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='open', required=True, readonly=True, tracking=True)
    expected_ids = fields.One2many('ab_accounting_opening_balance', 'run_id', copy=True)
    journal_ids = fields.One2many('ab_accounting_je_header', 'opening_run_id')
    closed_by = fields.Many2one('res.users', readonly=True)
    closed_at = fields.Datetime(readonly=True)

    def _editable(self):
        self._require_manager()
        self.check_access('write')
        self._serialize_stores(self.branch_id)
        self.invalidate_recordset()
        for rec in self:
            rec._check_scope(rec.company_id, rec.branch_id)
            if rec.state != 'open':
                raise UserError(_('The opening run is closed.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_manager()
        for vals in vals_list:
            if {'state', 'closed_by', 'closed_at', 'journal_ids'} & vals.keys():
                raise UserError(_('Opening run state is controlled by workflow actions.'))
            vals.update(state='open', closed_by=False, closed_at=False)
        recs = super().create(vals_list)
        for rec in recs:
            rec._check_scope(rec.company_id, rec.branch_id)
        return recs

    def write(self, vals):
        self._editable()
        if {'state', 'closed_by', 'closed_at', 'journal_ids', 'company_id', 'branch_id', 'accounting_date'} & vals.keys():
            raise UserError(_('Opening run scope, date and state cannot be edited.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Opening runs cannot be deleted.'))

    def reconciliation(self):
        self.ensure_one()
        self.check_access('read')
        self._check_scope(self.company_id, self.branch_id)
        domain = self.env['ab_accounting_report']._secured_domain(self.company_id, self.branch_id)
        lines = self.env['ab_accounting_je_line'].search(domain & fields.Domain('opening_run_id', '=', self.id))
        expected = defaultdict(float)
        actual = defaultdict(float)
        for row in self.expected_ids:
            expected[(row.account_id.id, row.partner_id.id, row.costcenter_id.id)] += row.expected_balance
        for line in lines:
            actual[(line.account_id.id, line.partner_id.id, line.costcenter_id.id)] += line.net_val
        result = []
        for key in sorted(set(expected) | set(actual)):
            account, partner, center = key
            result.append({'account_id': account, 'partner_id': partner, 'costcenter_id': center, 'expected': expected[key], 'actual': actual[key], 'difference': actual[key] - expected[key]})
        return result

    def action_close(self):
        with self.env.cr.savepoint():
            self._editable()
            for rec in self:
                journals = self.env['ab_accounting_je_header'].with_context(active_test=False).search(fields.Domain('opening_run_id', '=', rec.id))
                if not journals or any(j.state != 'posted' for j in journals):
                    raise ValidationError(_('All opening journals must be posted before closing the run.'))
                if any(float_compare(r['difference'], 0, precision_digits=2) for r in rec.reconciliation()):
                    raise ValidationError(_('Opening expected and posted balances do not reconcile.'))
            return super().write({'state': 'closed', 'closed_by': self.env.uid, 'closed_at': fields.Datetime.now()})

    def action_journal(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Opening Journals'), 'res_model': 'ab_accounting_je_header', 'view_mode': 'list,form', 'domain': [('opening_run_id', '=', self.id)], 'context': {'default_opening_run_id': self.id, 'default_branch_id': self.branch_id.id, 'default_company_id': self.company_id.id, 'default_accounting_date': str(self.accounting_date), 'default_event_type': 'opening'}}


class OpeningBalance(models.Model):
    _name = 'ab_accounting_opening_balance'
    _inherit = 'ab_accounting_scope'
    _description = 'Expected Opening Balance'
    run_id = fields.Many2one('ab_accounting_opening_run', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='run_id.company_id', store=True)
    branch_id = fields.Many2one(related='run_id.branch_id', store=True)
    account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', ondelete='restrict')
    costcenter_id = fields.Many2one('ab_costcenter', ondelete='restrict')
    expected_balance = fields.Float(digits=(16, 2), required=True)
    actual_balance = fields.Float(compute='_compute_actual', digits=(16, 2), compute_sudo=False)
    difference = fields.Float(compute='_compute_actual', digits=(16, 2), compute_sudo=False)
    _dimension_unique = models.Constraint('UNIQUE NULLS NOT DISTINCT(run_id, account_id, partner_id, costcenter_id)', 'Opening dimensions must be unique within a run.')

    @api.depends('expected_balance', 'run_id.journal_ids.state', 'account_id', 'partner_id', 'costcenter_id')
    def _compute_actual(self):
        results = {run.id: {(r['account_id'], r['partner_id'], r['costcenter_id']): r for r in run.reconciliation()} for run in self.run_id}
        for rec in self:
            row = results.get(rec.run_id.id, {}).get((rec.account_id.id, rec.partner_id.id, rec.costcenter_id.id), {})
            rec.actual_balance = row.get('actual', 0)
            rec.difference = rec.actual_balance - rec.expected_balance

    @api.model_create_multi
    def create(self, vals_list):
        self._require_manager()
        for vals in vals_list:
            if set(vals) - {'run_id', 'account_id', 'partner_id', 'costcenter_id', 'expected_balance'}:
                raise UserError(_('Opening balance scope is controlled by its run.'))
            vals['expected_balance'] = amount(vals.get('expected_balance', self.env.context.get('default_expected_balance', 0)))
        self.env['ab_accounting_opening_run'].browse(sorted({v['run_id'] for v in vals_list}))._editable()
        return super().create(vals_list)

    def write(self, vals):
        self.run_id._editable()
        if set(vals) - {'account_id', 'partner_id', 'costcenter_id', 'expected_balance'}:
            raise UserError(_('Opening balance scope is controlled by its run.'))
        if 'expected_balance' in vals:
            amount(vals['expected_balance'])
        return super().write(vals)

    def unlink(self):
        self.run_id._editable()
        return super().unlink()

    @api.constrains('account_id', 'partner_id', 'run_id')
    def _check_dimensions(self):
        for rec in self:
            if rec.account_id.company_id != rec.company_id or (rec.partner_id.company_id and rec.partner_id.company_id != rec.company_id):
                raise ValidationError(_('Opening dimensions must belong to the run company.'))
