from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


def _money(value):
    return round(float(value or 0.0), 2)


def _is_zero(value):
    return float_is_zero(value, precision_digits=2)


class PurchaseObHeaderAccounting(models.Model):
    _inherit = 'ab_purchase_ob_header'

    purchase_accounting_journal_id = fields.Many2one(
        'ab_accounting_je_header',
        readonly=True,
        copy=False,
        ondelete='restrict',
        string='Accounting Journal',
    )
    purchase_accounting_journal_count = fields.Integer(compute='_compute_purchase_accounting_journal_count')

    @api.depends('purchase_accounting_journal_id')
    def _compute_purchase_accounting_journal_count(self):
        for rec in self:
            rec.purchase_accounting_journal_count = 1 if rec.purchase_accounting_journal_id else 0

    def action_view_purchase_accounting_journal(self):
        self.ensure_one()
        if not self.purchase_accounting_journal_id:
            raise UserError(_('No accounting journal is linked to this receipt document.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accounting Journal'),
            'res_model': 'ab_accounting_je_header',
            'res_id': self.purchase_accounting_journal_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def btn_submit_inventory(self):
        self.ensure_one()
        if self.status == 'saved':
            return super().btn_submit_inventory()
        with self.env.cr.savepoint():
            result = super().btn_submit_inventory()
            self.invalidate_recordset(['status', 'purchase_accounting_journal_id'])
            if self.status == 'saved' and self.purpose == 'non_purchase_receipt':
                self._post_purchase_accounting_non_purchase_receipt()
            return result

    def _post_purchase_accounting_non_purchase_receipt(self):
        self.ensure_one()
        if self.purchase_accounting_journal_id:
            return self.purchase_accounting_journal_id
        if self.purpose != 'non_purchase_receipt':
            return self.env['ab_accounting_je_header']

        accounting_date = self.doc_date or fields.Date.context_today(self)
        config = self.env['ab_purchase_accounting_config']._for_branch_date(
            self.env.company,
            self.store_id,
            accounting_date,
        )
        config = config._with_posting_user()
        offset_account = config._non_purchase_receipt_offset_account(self.receipt_type_id)
        amount = _money(self.total_cost)
        if _is_zero(amount):
            raise ValidationError(_('Non-purchase receipts require a nonzero receipt value for accounting.'))
        if amount < 0:
            raise ValidationError(_('Non-purchase receipt accounting amounts cannot be negative.'))

        reference = '%s %s' % (_('Non-purchase receipt'), self.doc_code or self.id)
        lines = [
            self._purchase_ob_accounting_line(
                config,
                config.inventory_account_id,
                debit=amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=accounting_date,
            ),
            self._purchase_ob_accounting_line(
                config,
                offset_account,
                credit=amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=accounting_date,
            ),
        ]
        config._check_configuration()
        if config.branch_id != self.store_id:
            raise ValidationError(_('Accounting configuration must match the document branch.'))
        header_line = next((line for line in lines if line['account_id'] == config.supplier_account_id.id), lines[-1])
        request = {
            'account_id': header_line['account_id'],
            'costcenter_id': header_line['costcenter_id'],
            'store_id': config.branch_id.id,
            'doctype_id': config.purchase_doctype_id.id,
            'posted_date': accounting_date,
            'res_header_ref': self._name,
            'res_header_id': self.id,
            'lines': lines,
        }
        posting_context = dict(self.env.context, allowed_company_ids=[config.company_id.id])
        journal = self.env['ab_accounting_je_header'].with_user(config.posting_user_id).with_context(
            posting_context
        ).post_journal(request)
        self.write({'purchase_accounting_journal_id': journal.id})
        return journal

    def _purchase_ob_accounting_line(
        self,
        config,
        account,
        debit=0.0,
        credit=0.0,
        explain=None,
        doc_no=None,
        accounting_date=None,
    ):
        self.ensure_one()
        costcenter = config.default_costcenter_id if account.has_costcenter else False
        if account.has_costcenter and not costcenter:
            raise ValidationError(
                _('Account %(account)s requires a cost center. Configure a default cost center on the adapter.')
                % {'account': account.display_name}
            )
        accounting_date = accounting_date or self.doc_date or fields.Date.context_today(self)
        return {
            'account_id': account.id,
            'store_id': config.branch_id.id,
            'costcenter_id': costcenter.id if costcenter else False,
            'explain': explain or _('Non-purchase receipt accounting'),
            'doc_no': doc_no or self.doc_code or str(self.id),
            'due_date': accounting_date + timedelta(days=config.supplier_due_days) if account.has_due_date else False,
            'debit_val': _money(debit),
            'credit_val': _money(credit),
        }
