# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import datetime
import logging

_logger = logging.getLogger(__name__)


class AccountStatementReport(models.Model):
    _name = 'ab_accounting_account_statement'
    _description = "Account statement Report"

    start_date = fields.Date(string="Final Date", default=fields.Date.today() - relativedelta(months=-1))
    end_date = fields.Date(string="Final Date To", default=fields.Date.today() + relativedelta(years=+10))
    start_date_due = fields.Date(string="Due Date", )
    end_date_due = fields.Date(string="Due Date To", )
    start_date_posted = fields.Date(string="Posted Date", )
    end_date_posted = fields.Date(string="Posted Date To", )
    start_date_sett = fields.Date(string="Settlement Date", )
    end_date_sett = fields.Date(string="Settlement Date To", )
    html = fields.Html(string='HTML')
    report_field_ids = fields.Many2many('ir.model.fields',
                                        string='report Fields',
                                        domain=[('model', '=', 'ab_accounting_je_line_qry')])
    parent_account_id = fields.Many2one("ab_accounting_account_guide")
    account_ids = fields.Many2many("ab_accounting_account_guide",
                                   domain=[('is_final', '=', True)])
    costcenter_id = fields.Many2one('ab_costcenter', )
    creator_ids = fields.Many2many('res.users')
    store_id = fields.Many2one('ab_store')
    is_posted = fields.Boolean(default=True)

    @api.model
    def create(self, vals_list):
        rec = super().create(vals_list)
        # self._set_default()
        return rec

    def write(self, vals):
        res = super().write(vals)
        # self._set_default()
        return res

    def _set_default(self):
        flds = self.env['ir.model.fields'].sudo().search([('model', '=', self._name)])
        for fld in flds:
            value = getattr(self, fld.name)
            json_value = self._get_json_value(fld, value)
            if not fld.readonly and json_value:
                self.env['ir.default'].sudo().set(model_name=self._name, field_name=fld.name, value=json_value,
                                                  user_id=self.env.uid,
                                                  company_id=False, condition=False)

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
        action = self.env.ref('ab_accounting.action_export_account_statement_excel')
        action[0].name = "Account Statement"
        return action.report_action(self)

    def btn_browse_account_statement(self):
        data = self.get_account_statement_data()
        if data['moves_count'] > 200:
            data['rows'] = data['rows'][0:200]
            data['rows_count_warning'] = _(f"Report has {data['moves_count']}, Only 200 lines can be shown.")
        html = self.env.ref('ab_accounting.template_account_statement_report')._render(data)
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
            account_guide = self.env['ab_accounting_account_guide']
            if not self.report_field_ids:
                self.report_field_ids = self.report_field_ids.sudo().search(
                    [('name', 'in', ["debit_val", "credit_val", "parent_account_id", "account_id",
                                     "store_id", "costcenter_id", "due_date",
                                     "final_date", "explain"])])
                self.env.cr.commit()
            report_flds = self.report_field_ids.mapped('name')
            headers = [self._get_fld_string(fld) for fld in report_flds]
            domain = []
            balance_domain = []

            children_account_ids = account_guide.with_context(active_test=False).search(
                [('id', 'child_of', self.parent_account_id.id)]).ids
            accounts = self.env['ab_accounting_account_guide'].with_context(active_test=False).browse(
                self.account_ids.ids + children_account_ids)

            if accounts:
                domain.append(('account_id', 'in', accounts.ids))
                balance_domain.append(('account_id', 'in', accounts.ids))

            if self.costcenter_id:
                domain.append(('costcenter_id', '=', self.costcenter_id.id))
                balance_domain.append(('costcenter_id', '=', self.costcenter_id.id))

            if self.is_posted:
                domain.append(('is_posted', '=', True))
                balance_domain.append(('is_posted', '=', True))

            if self.store_id:
                domain.append(('store_id', '=', self.store_id.id))

            if self.creator_ids:
                domain.append(('create_uid', 'in', self.creator_ids.ids))

            if self.start_date_due:
                domain.append(('due_date', '>=', self.start_date_due))
            if self.end_date_due:
                domain.append(('due_date', '<=', self.start_date_due))

            if self.start_date_posted:
                domain.append(('posted_date', '>=', self.start_date_posted))
            if self.end_date_posted:
                domain.append(('posted_date', '<=', self.end_date_posted))

            if self.start_date_sett:
                domain.append(('settlement_date', '>=', self.start_date_sett))
            if self.end_date_sett:
                domain.append(('settlement_date', '<=', self.end_date_sett))

            if self.costcenter_id:
                domain.append(('costcenter_id', '=', self.costcenter_id.id))
            if not domain:
                raise UserError(_("You must choose at least one criteria"))

            start_date = self.start_date or datetime.date(year=2000, month=1, day=1)
            end_date = self.end_date or datetime.date(year=2050, month=1, day=1)

            opening_balance_groups = je.read_group(domain=balance_domain + [('final_date', '<', start_date)],
                                                   groupby=['account_id'],
                                                   fields=['account_id', 'net_val:sum'])
            opening_balance_dict = {
                group['account_id'][0]: group['net_val']
                for group in opening_balance_groups}

            start_balance = sum(bal['net_val'] for bal in opening_balance_groups)

            domain.append(('final_date', '>=', start_date))

            domain.append(('final_date', '<=', end_date))

            moves = je.search(domain, order=' account_id asc,final_date asc')

            total_moves = sum(line.debit_val - line.credit_val
                              for line in je.search(domain))

            end_balance = start_balance + total_moves

            rows = []
            running_total = 0

            for move in moves:
                account = move.account_id
                if account.id in opening_balance_dict:
                    opening_balance = opening_balance_dict.get(account.id, 0)
                    running_total = opening_balance
                    opening_row = tuple(
                        self._get_fld_value(move, fld, opening_balance=round(opening_balance, 2))
                        for fld in
                        report_flds)
                    rows.append(opening_row)
                    opening_balance_dict.pop(account.id, None)

                if move.net_val != 0:
                    running_total += move.debit_val - move.credit_val
                    row = tuple(self._get_fld_value(move, fld) for fld in report_flds)
                    row += (round(running_total, 2),)
                    rows.append(row)

            # add opening balance lines for accounts that does not have moves
            je = self.env['ab_accounting_je_line_qry']
            for account_id in opening_balance_dict:
                move = je.search([('account_id', '=', account_id)], limit=1)
                opening_balance = opening_balance_dict.get(account_id, 0)
                opening_row = tuple(
                    self._get_fld_value(move, fld, opening_balance=round(opening_balance, 2))
                    for fld in
                    report_flds)
                rows.append(opening_row)



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
            fld_string = self.env['ir.translation'].get_field_string(model_name)[fld]
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
