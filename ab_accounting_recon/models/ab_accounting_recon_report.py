# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import datetime
import logging

_logger = logging.getLogger(__name__)


class AccountingReconReport(models.Model):
    _name = 'ab_accounting_recon_header'
    _inherit = "ab_accounting_recon_header"

    start_date = fields.Date(string="Final Date", default=fields.Date.today() - relativedelta(months=-1))
    end_date = fields.Date(string="Final Date To", default=fields.Date.today() + relativedelta(years=+10))
    html = fields.Html(string='HTML')
    report_field_ids = fields.Many2many('ir.model.fields',
                                        string='report Fields',
                                        domain=[('model', '=', 'ab_accounting_je_line_qry')])

    @staticmethod
    def _get_json_value(fld, value):
        if value:
            if fld.ttype == 'many2one':
                return value.id
            elif fld.ttype == 'date':
                return value.strftime('%Y-%m-%d')
            elif fld.ttype in {'text', 'char', 'float', 'integer'}:
                return value
        return None

    ################################################################################
    def btn_export_excel_account_statement(self):
        action = self.env.ref('ab_accounting_recon.action_export_accounting_recon_excel')
        action[0].name = "Account Statement"
        return action.report_action(self)

    def btn_browse_account_statement(self):
        data = self.get_account_statement_data()
        if data['moves_count'] > 200:
            data['rows'] = data['rows'][0:200]
            data['rows_count_warning'] = _(f"Report has {data['moves_count']}, Only 200 lines can be shown.")
        html = self.env['ir.qweb']._render('ab_accounting.template_account_statement_report', data)
        self.write({'html': html})

    def btn_print_pdf_account_statement(self):
        action = self.env.ref('ab_accounting.action_print_account_statement_pdf')
        data = self.get_account_statement_data()
        if data['moves_count'] > 200:
            raise UserError(_("Too many rows, can not browse!"))
        return action.report_action(self, data=data)

    def get_account_statement_data(self):
        try:
            je = self.env['ab_accounting_je_line_qry']
            if not self.report_field_ids:
                self.report_field_ids = self.report_field_ids.sudo().search(
                    [('name', 'in', ["debit_val", "credit_val", "account_id",
                                     "store_id", "costcenter_id", "due_date",
                                     "final_date", "explain"])])
                self.env.cr.commit()
            report_flds = self.report_field_ids.mapped('name')
            headers = [self._get_fld_string(fld) for fld in report_flds]
            domain = [
                ('account_id', '=', self.account_id.id),
                ('is_posted', '=', True)
            ]

            start_date = self.start_date or datetime.date(year=2000, month=1, day=1)
            end_date = self.end_date or datetime.date(year=2050, month=1, day=1)

            opening_balance_groups = je.read_group(domain=domain + [('final_date', '<', start_date)],
                                                   groupby=['account_id'],
                                                   fields=['account_id', 'net_val:sum'])
            opening_balance_dict = {
                group['account_id'][0]: group['net_val']
                for group in opening_balance_groups
            }

            start_balance = sum(bal['net_val'] for bal in opening_balance_groups)

            domain.append(('final_date', '>=', start_date))

            domain.append(('final_date', '<=', end_date))

            moves = je.search(domain, order=' account_id asc,final_date asc')

            total_moves = sum(line.debit_val - line.credit_val
                              for line in je.search(domain))

            end_balance = start_balance + total_moves

            rows = []
            running_total = 0
            account_id = 0
            for move in moves:
                if not move.account_id.id == account_id:
                    account_id = move.account_id.id
                    opening_balance = opening_balance_dict.get(account_id, 0)
                    running_total = opening_balance
                    opening_row = tuple(
                        self._get_fld_value(move, fld, opening_balance=round(opening_balance, 2)) for fld in
                        report_flds)
                    rows.append(opening_row)
                if move.net_val != 0:
                    running_total += move.debit_val - move.credit_val
                    row = tuple(self._get_fld_value(move, fld) for fld in report_flds)
                    row += (round(running_total, 2),)
                    rows.append(row)
        except Exception as ex:
            raise UserError(repr(ex))

        return {
            'description': 'Report Name',
            'start_balance': start_balance,
            'end_balance': end_balance,
            'start_date': start_date,
            'end_date': end_date,
            'headers': headers,
            'rows': rows,
            'moves_count': len(rows),
        }

    def _get_fld_string(self, fld):
        fld_string = ""
        try:
            model_name = 'ab_accounting_je_line_qry'
            fld_string = self.env[model_name]._fields[fld]._description_string(self.env)
            fld_string = fld_string or fld
        except Exception as ex:
            _logger.warning(str(ex))
        return fld_string or fld

    def _get_fld_value(self, move, fld, opening_balance=False):
        if opening_balance is not False:
            if fld == 'debit_val':
                return opening_balance > 0 and opening_balance or 0
            elif fld == 'credit_val':
                return opening_balance <= 0 and opening_balance * -1 or 0
            elif fld == 'net_val':
                return opening_balance or 0
            elif fld in {'due_date', 'settlement_date', 'final_date', 'posted_date'}:
                return self.start_date
            elif fld in {'due_date', 'settlement_date', 'final_date', 'posted_date'}:
                return self.start_date
            elif fld in {'store_id', 'costcenter_id'}:
                return "_"
            elif fld in {'explain'}:
                return _("Opening Balance")

        line_fields = move._fields
        field = line_fields[fld]
        field_type = field.__class__.__name__
        if field_type == 'Many2one':
            field_many2one = getattr(move, fld)
            name = field_many2one._rec_name
            return getattr(field_many2one, name)
        else:
            return getattr(move, fld)
