from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountingAccountGuide(models.Model):
    _name = 'ab_accounting_account_guide'
    _inherit = 'ab_accounting_account_guide'

    recon_account_id = fields.Many2one('ab_accounting_account_guide',
                                       domain=[('is_final', '=', True)],
                                       compute='_compute_recon_account_id',
                                       store=True,
                                       readonly=False)

    prevent_access_directly = fields.Boolean(default=False,
                                             compute='_compute_prevent_access_directly',
                                             store=True,
                                             readonly=False)

    @api.depends('reconcile')
    def _compute_prevent_access_directly(self):
        for rec in self:
            prevent_access_directly = rec.reconcile
            if rec.prevent_access_directly != prevent_access_directly:
                rec.prevent_access_directly = prevent_access_directly

    @api.depends('reconcile')
    def _compute_recon_account_id(self):
        for rec in self:
            if not rec.reconcile:
                rec.recon_account_id = False


class AbAccountingJeLine(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = 'ab_accounting_je_line'

    recon_account_id = fields.Many2one(related='account_id.recon_account_id')

    def write(self, values):
        allow_recon = self.env.context.get('allow_recon')
        old_accounts = self.account_id
        res = super().write(values)
        all_accounts = self.account_id | old_accounts
        prevent_upd = {'account_id', 'settlement_date'}
        if not allow_recon:
            if prevent_upd.intersection(values):
                for account in all_accounts:
                    if account.reconcile and account.prevent_access_directly:
                        raise ValidationError(_(f"\n- You Can not use Reconcile Account Directly."))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_accounting_recon_abaccountingjeline(values)
        return records

    def _create_one_ab_accounting_recon_abaccountingjeline(self, values):
        res = super().create(values)
        allow_recon = self.env.context.get('allow_recon')
        if not allow_recon:
            if res.account_id.reconcile and res.account_id.prevent_access_directly:
                raise ValidationError(_(f"\n- You Can not use Reconcile Account Directly."))

        return res


class AbAccountingJeLineQry(models.Model):
    _name = 'ab_accounting_je_line_qry'
    _inherit = 'ab_accounting_je_line_qry'

    recon_account_id = fields.Many2one(related='account_id.recon_account_id')

# class AbAccountingJeHeader(models.Model):
#     _name = 'ab_accounting_je_header'
#     _inherit = 'ab_accounting_je_header'
#
#     def _msg_is_lines_ok(self, lines):
#         msg = super()._msg_is_lines_ok(lines)
#         if self.res_header_ref == 'ab_accounting_recon_header':
#             return msg
#         for line in lines:
#             if line.account_id.reconcile and line.account_id.prevent_access_directly:
#                 msg += _(f"\n- You Can not use Reconcile Account Directly.")
#
#         return msg
