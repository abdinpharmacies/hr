from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


def _money(value):
    return round(float(value or 0.0), 2)


def _is_zero(value):
    return float_is_zero(value, precision_digits=2)


class PurchaseHeader(models.Model):
    _inherit = 'ab_purchase_header'

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
            raise UserError(_('No accounting journal is linked to this purchase invoice.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accounting Journal'),
            'res_model': 'ab_accounting_je_header',
            'res_id': self.purchase_accounting_journal_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def btn_save_inventory(self):
        self.ensure_one()
        if self.status == 'saved':
            return super().btn_save_inventory()
        with self.env.cr.savepoint():
            result = super().btn_save_inventory()
            self.invalidate_recordset(['status', 'purchase_accounting_journal_id'])
            if self.status == 'saved':
                self._post_purchase_accounting_receipt()
            return result

    def _post_purchase_accounting_receipt(self):
        self.ensure_one()
        if self.purchase_accounting_journal_id:
            return self.purchase_accounting_journal_id

        config = self._purchase_accounting_config()
        supplier_total = _money(self.net_invoice or self.total_cost)
        tax_amount = _money(self.net_tax or self.total_tax)
        inventory_amount = _money(supplier_total - tax_amount)
        self._validate_purchase_accounting_amounts(supplier_total, tax_amount, inventory_amount)
        if _is_zero(supplier_total):
            return self.env['ab_accounting_je_header']

        reference = self._purchase_accounting_reference(_('Purchase receipt'))
        lines = []
        if not _is_zero(inventory_amount):
            lines.append(self._purchase_accounting_line(
                config,
                config.inventory_account_id,
                debit=inventory_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        if not _is_zero(tax_amount):
            if not config.tax_account_id:
                raise ValidationError(_('Configure a purchase tax account before posting taxed purchases.'))
            lines.append(self._purchase_accounting_line(
                config,
                config.tax_account_id,
                debit=tax_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        lines.append(self._purchase_accounting_line(
            config,
            config.supplier_account_id,
            credit=supplier_total,
            explain=reference,
            doc_no=self.doc_code or str(self.id),
            accounting_date=self.doc_date or fields.Date.context_today(self),
        ))

        journal = self._post_purchase_accounting_journal(
            config,
            doctype=config.purchase_doctype_id,
            event_type='purchase_receipt',
            operation_suffix='receipt',
            reference=reference,
            lines=lines,
        )
        self.write({'purchase_accounting_journal_id': journal.id})
        return journal

    def _purchase_accounting_config(self):
        self.ensure_one()
        config = self.env['ab_purchase_accounting_config']._for_branch_date(
            self.env.company,
            self.store_id,
            self.doc_date or fields.Date.context_today(self),
        )
        return config._with_posting_user()

    def _validate_purchase_accounting_amounts(self, supplier_total, tax_amount, inventory_amount):
        if supplier_total < 0 or tax_amount < 0 or inventory_amount < 0:
            raise ValidationError(_('Purchase accounting amounts cannot be negative.'))

    def _purchase_accounting_reference(self, label):
        self.ensure_one()
        return '%s %s' % (label, self.doc_code or self.id)

    def _purchase_accounting_costcenter(self, config):
        self.ensure_one()
        return self.supplier_id.costcenter_id or config.default_costcenter_id

    def _purchase_accounting_due_date(self, config, accounting_date=None):
        self.ensure_one()
        accounting_date = accounting_date or self.doc_date or fields.Date.context_today(self)
        return accounting_date + timedelta(days=config.supplier_due_days)

    def _purchase_accounting_line(
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
        if account.has_partner:
            raise ValidationError(
                _('Account %(account)s requires a partner, but purchase suppliers are not linked to partners.')
                % {'account': account.display_name}
            )
        costcenter = self._purchase_accounting_costcenter(config) if account.has_costcenter else False
        if account.has_costcenter and not costcenter:
            raise ValidationError(
                _('Account %(account)s requires a cost center. Configure one on the supplier or adapter.')
                % {'account': account.display_name}
            )
        return {
            'account_id': account.id,
            'costcenter_id': costcenter.id if costcenter else False,
            'explain': explain or self._purchase_accounting_reference(_('Purchase accounting')),
            'doc_no': doc_no or self.doc_code or str(self.id),
            'due_date': self._purchase_accounting_due_date(
                config, accounting_date=accounting_date
            ) if account.has_due_date else False,
            'debit_val': _money(debit),
            'credit_val': _money(credit),
        }

    def _post_purchase_accounting_journal(
        self,
        config,
        doctype,
        event_type,
        operation_suffix,
        reference,
        lines,
        source=None,
        accounting_date=None,
        source_reference=None,
    ):
        self.ensure_one()
        source = source or self
        source_reference = source_reference or self.doc_code or str(self.id)
        accounting_date = accounting_date or self.doc_date or fields.Date.context_today(self)
        request = {
            'origin_database': self.env.cr.dbname,
            'operation_identity': '%s:%s:%s' % (source._name, source.id, operation_suffix),
            'company_id': config.company_id.id,
            'branch_id': config.branch_id.id,
            'doctype_id': doctype.id,
            'accounting_date': accounting_date,
            'source_model': source._name,
            'source_res_id': source.id,
            'source_reference': source_reference,
            'event_type': event_type,
            'reference': reference,
            'lines': lines,
        }
        posting_context = dict(self.env.context, allowed_company_ids=[config.company_id.id])
        return self.env['ab_accounting_je_header'].with_user(config.posting_user_id).with_context(
            posting_context
        ).post_journal(request)


class PurchaseNoticeHeader(models.Model):
    _inherit = 'ab_purchase_notice_header'

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
            raise UserError(_('No accounting journal is linked to this purchase return.'))
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
            if self.status == 'saved':
                self._post_purchase_accounting_return()
            return result

    def _post_purchase_accounting_return(self):
        self.ensure_one()
        if self.purchase_accounting_journal_id:
            return self.purchase_accounting_journal_id
        notice_effect = self.notice_effect or 'physical'
        if notice_effect == 'physical' and self.notice_type != 'credit_notice':
            return self.env['ab_accounting_je_header']

        config = self.env['ab_purchase_accounting_config']._for_branch_date(
            self.env.company,
            self.store_id,
            self.doc_date or fields.Date.context_today(self),
        )
        config = config._with_posting_user()
        supplier_total = _money(self.total_cost)
        tax_amount = _money(self.total_taxes_value)
        inventory_amount = _money(supplier_total - tax_amount)
        self.purchase_header_id._validate_purchase_accounting_amounts(supplier_total, tax_amount, inventory_amount)
        if _is_zero(supplier_total):
            return self.env['ab_accounting_je_header']

        if notice_effect == 'financial' and self.notice_type == 'debit_notice':
            reference = '%s %s' % (_('Purchase financial debit notice'), self.doc_code or self.id)
            doctype = config.purchase_doctype_id
            event_type = 'purchase_financial_debit_notice'
            operation_suffix = 'financial_debit:%s' % self.id
            lines = self._purchase_accounting_positive_notice_lines(
                config, supplier_total, tax_amount, inventory_amount, reference,
            )
        else:
            label = _('Purchase financial credit notice') if notice_effect == 'financial' else _('Purchase return')
            reference = '%s %s' % (label, self.doc_code or self.id)
            doctype = config.return_doctype_id
            event_type = 'purchase_financial_credit_notice' if notice_effect == 'financial' else 'purchase_return'
            operation_suffix = (
                'financial_credit:%s' % self.id
                if notice_effect == 'financial'
                else 'return:%s' % self.id
            )
            lines = self._purchase_accounting_negative_notice_lines(
                config, supplier_total, tax_amount, inventory_amount, reference,
            )

        journal = self.purchase_header_id._post_purchase_accounting_journal(
            config,
            doctype=doctype,
            event_type=event_type,
            operation_suffix=operation_suffix,
            reference=reference,
            lines=lines,
            source=self,
            accounting_date=self.doc_date or fields.Date.context_today(self),
            source_reference=self.doc_code or str(self.id),
        )
        self.write({'purchase_accounting_journal_id': journal.id})
        return journal

    def _purchase_accounting_negative_notice_lines(
        self, config, supplier_total, tax_amount, inventory_amount, reference,
    ):
        self.ensure_one()
        lines = [
            self.purchase_header_id._purchase_accounting_line(
                config,
                config.supplier_account_id,
                debit=supplier_total,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            )
        ]
        if not _is_zero(tax_amount):
            if not config.tax_account_id:
                raise ValidationError(_('Configure a purchase tax account before posting taxed purchase notices.'))
            lines.append(self.purchase_header_id._purchase_accounting_line(
                config,
                config.tax_account_id,
                credit=tax_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        if not _is_zero(inventory_amount):
            lines.append(self.purchase_header_id._purchase_accounting_line(
                config,
                config.inventory_account_id,
                credit=inventory_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        return lines

    def _purchase_accounting_positive_notice_lines(
        self, config, supplier_total, tax_amount, inventory_amount, reference,
    ):
        self.ensure_one()
        lines = []
        if not _is_zero(inventory_amount):
            lines.append(self.purchase_header_id._purchase_accounting_line(
                config,
                config.inventory_account_id,
                debit=inventory_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        if not _is_zero(tax_amount):
            if not config.tax_account_id:
                raise ValidationError(_('Configure a purchase tax account before posting taxed purchase notices.'))
            lines.append(self.purchase_header_id._purchase_accounting_line(
                config,
                config.tax_account_id,
                debit=tax_amount,
                explain=reference,
                doc_no=self.doc_code or str(self.id),
                accounting_date=self.doc_date or fields.Date.context_today(self),
            ))
        lines.append(self.purchase_header_id._purchase_accounting_line(
            config,
            config.supplier_account_id,
            credit=supplier_total,
            explain=reference,
            doc_no=self.doc_code or str(self.id),
            accounting_date=self.doc_date or fields.Date.context_today(self),
        ))
        return lines
