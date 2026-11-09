from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountingReconLine(models.Model):
    _name = 'ab_accounting_recon_line'
    _description = 'ab_accounting_recon_wiz_line'

    header_id = fields.Many2one('ab_accounting_recon_header')

    je_line_id = fields.Many2one('ab_accounting_je_line')
    debit_val = fields.Float(related='je_line_id.debit_val')
    credit_val = fields.Float(related='je_line_id.credit_val')
    due_date = fields.Date(related='je_line_id.due_date')
    doc_no = fields.Char(related='je_line_id.doc_no')
    explain = fields.Text(related='je_line_id.explain')
    account_id = fields.Many2one(related='je_line_id.account_id')
    costcenter_id = fields.Many2one(related='je_line_id.costcenter_id')
    store_id = fields.Many2one(related='je_line_id.store_id')
    is_posted = fields.Boolean(related='je_line_id.is_posted')
    is_confirmed = fields.Boolean(related='je_line_id.is_confirmed')
    is_frozen = fields.Boolean(related='je_line_id.is_frozen')
    je_settlement_date = fields.Date(related='je_line_id.settlement_date', string='Settlement Date')
    account_balance = fields.Float(compute='_compute_account_balance')

    settlement_date = fields.Date(string='Set Settlement')

    def _compute_account_balance(self):
        for rec in self:
            jes = self.env['ab_accounting_je_line'].search([
                ('account_id', '=', rec.account_id.id),
                ('is_posted', '=', True),
            ])
            rec.account_balance = sum(je.net_val for je in jes)

    def btn_delete_recon_je_line(self):
        if self.je_line_id.settlement_date:
            raise ValidationError(_("Can not remove this line, it is already reconciled!"))
        else:
            self.unlink()

    def btn_reconcile_account(self):
        self = self.with_context(from_header=True, sudo_confirm=True, allow_recon=True)
        self.ensure_one()
        if not self.settlement_date:
            raise ValidationError(_("You must set settlement date."))

        recon_account_id = self.je_line_id.account_id.recon_account_id.id
        if not recon_account_id:
            raise ValidationError(_("Account must have reconcile account."))

        self.je_line_id.account_id = recon_account_id
        self.je_line_id.settlement_date = self.settlement_date
        explain = self.je_line_id.explain
        self.je_line_id.explain = f"{explain} - reconcile"

    _ab_accounting_recon_line_unique = models.Constraint('unique(je_line_id,header_id)', 'JE Line CAN NOT BE DUPLICATED!')


class AccountingReconHeader(models.Model):
    _name = 'ab_accounting_recon_header'
    _inherit = ['ab_accounting_je_header_delegate_common']
    _description = 'ab_accounting_recon_header'
    _order = 'id DESC'

    je_header_account_id = fields.Many2one(related='je_header_id.account_id',
                                           readonly=False,
                                           required=True,
                                           domain=lambda self: self._get_domain_recon_account_ids())
    recon_je_line_ids = fields.One2many('ab_accounting_recon_line', 'header_id', )
    settlement_date = fields.Date()
    je_line_search_ids = fields.Many2many(
        comodel_name='ab_accounting_je_line',
        relation='ab_accounting_recon_accounting_je_line_rel',
        column1='recon_header_id',
        column2='je_line_id',
        string='JE Search',
    )
    find_by = fields.Selection(
        selection=[
            ('doc_code_and_value', 'Document Code And Value'),
            ('eplus_serial', 'e-Plus Serial'),
        ], default='doc_code_and_value')

    excel_text = fields.Text()

    recon_has_lines = fields.Boolean(compute='_compute_recon_has_lines')

    def _get_domain_recon_account_ids(self):
        accounts_with_recon = self.env['ab_accounting_account_guide'].search([('recon_account_id', '!=', False)])
        recon_accounts = accounts_with_recon.mapped('recon_account_id')
        return [('id', 'in', recon_accounts.ids)]

    @api.depends('recon_je_line_ids')
    def _compute_recon_has_lines(self):
        for record in self:
            record.recon_has_lines = bool(record.recon_je_line_ids)

    def btn_set_settlement_date_for_all(self):
        self.recon_je_line_ids.settlement_date = self.settlement_date

    def btn_reconcile_all(self):
        for rec in self.recon_je_line_ids:
            rec.btn_reconcile_account()

    def btn_add_to_reconcile(self):
        je_ids = self.je_line_search_ids.ids
        recon_lines = self.env['ab_accounting_recon_line'].sudo().with_context(active_test=False).search(
            [('header_id', '=', self.id)]
        )

        recon_lines_set = set(recon_lines.mapped('je_line_id.id'))
        self.write({'recon_je_line_ids': [
            (0, 0, {'je_line_id': je_id})
            for je_id in je_ids
            if je_id not in recon_lines_set
        ]})

    def btn_freeze(self):
        self.je_header_id.btn_freeze()

    def btn_unfreeze(self):
        self.je_header_id.btn_unfreeze()

    def btn_post_je(self):
        self.je_header_id.btn_post_je()

    def btn_confirm_all_je(self):
        self.je_header_id.btn_confirm_all_je()

    def write(self, values):
        res = super(AccountingReconHeader, self.with_context(allow_recon=True)).write(values)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_accounting_recon_accountingreconheader(values)
        return records

    def _create_one_ab_accounting_recon_accountingreconheader(self, values):
        values.update({'account_id': values['je_header_account_id']})
        res = super(AccountingReconHeader, self.with_context(allow_recon=True)).create(values)
        return res
