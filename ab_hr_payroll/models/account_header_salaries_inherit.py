import datetime
from dateutil.relativedelta import relativedelta
import itertools

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero, float_round
from .last_day_of_month import last_day_of_month


class SalariesMoves(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = 'ab_accounting_je_header'

    je_type = fields.Selection([('pay', 'Pay with Bank Transfer'),
                                ('pay_cash', 'Pay with Cash'),
                                ('deduction', 'Deductions'),
                                ('firing', 'Firing'),
                                ],
                               groups='ab_accounting.group_ab_accounting_manager')

    due_month = fields.Date(groups='ab_accounting.group_ab_accounting_manager', )

    costcenter_codes = fields.Text()
    allowed_negative = fields.Boolean(default=False)

    @api.constrains('due_month')
    def _constraint_ab_accounting_je_header_salary_vars(self):
        for rec in self:
            salary_month = self._calc_salary_month()
            message = _(f"Invalid salary month, it supposed to be {format(salary_month, '%B-%y')}")

            if rec.due_month and rec.due_month.replace(day=1) > fields.Date.today():
                raise ValidationError(message)

    @api.onchange("due_month")
    def _onchange_ab_accounting_je_header_due_month(self):
        if self.due_month:
            salary_month = self._calc_salary_month()
            message = _(f"Please check salary month, it supposed to be {format(salary_month, '%B-%y')}")
            title = _("Attention ⚠️")
            if self.due_month and self.due_month > salary_month:
                # any 'type' will be a notification even 'abz d8e@#' , no way to make it sticky
                return {
                    "warning": {
                        'type': 'notification',
                        'title': title,
                        'message': message,
                    }
                }

    def _calc_salary_month(self):
        today = fields.Date.today()
        if today.day < 21:
            salary_month = today.replace(day=1) - relativedelta(months=1)
        else:
            salary_month = today.replace(day=1)

        return salary_month

    def btn_create_je(self):
        # if only one record in line_ids, remove it.
        if len(self.line_ids) == 1:
            self.write({"line_ids": [(5,)]})

        if self.je_type == 'deduction':
            self.create_deductions(je_type='deduction')

        elif self.je_type == 'firing':
            self.create_deductions(je_type='firing')

        elif self.je_type == 'pay':
            self._create_payment_for_bank()

        elif self.je_type == 'pay_cash':
            self._create_payment_for_cash()

    def create_deductions(self, je_type, all_employees=False):
        store_id = 78
        due_salaries_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries').id
        firing_parent_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_firing_parent').id
        precision = 0.01

        due_salaries_account_id = due_salaries_account_id

        if je_type not in ['deduction', 'firing']:
            raise ValidationError(_(f"JE Type not in the list {('deduction', 'firing')}"))

        # check if from wizard
        costcenters_working = self.env['ab_hr_employee'].search([('internal_working_employee', '=', True)]).mapped(
            'costcenter_id')
        if not all_employees:
            costcenter_codes_list = self.costcenter_codes.strip().split('\n')
            costcenter_ids = self.env['ab_costcenter'].search([('code', 'in', costcenter_codes_list)]).ids
            header_je = self
        # check if schedule
        else:

            costcenters_forbidden = self.env['ab_costcenter_deduction_forbidden'].search([]).mapped('costcenter_id')
            costcenters = costcenters_working - costcenters_forbidden
            costcenter_ids = costcenters.ids
            costcenter_admin_id = self.env['ab_costcenter'].search([('code', '=', '1')]).id

            header_je = self.env['ab_accounting_je_header'].create(
                {
                    "account_id": due_salaries_account_id,
                    "costcenter_id": costcenter_admin_id,
                    "doctype_id": 7,
                }
            )

        # costcenter domain if schedule or from wizard
        domain = [
            ('costcenter_id', 'in', costcenter_ids),
        ]

        salary_month = header_je._calc_salary_month()
        due_date = header_je.due_month and header_je.due_month.replace(day=1) or salary_month
        explain = ""
        if je_type == 'deduction':
            domain.append(('due_date', '<=', last_day_of_month(due_date)))
            domain.append(('account_id.salary_deduction', '=', True))
            explain = _("Auto JE for deductions")

        if je_type == 'firing':
            domain.append(('account_id.parent_id', '=', firing_parent_account_id))  # سلف وعهد وخصومات
            explain = _("Auto JE for Firing")
            working_and_firing_costcenter_ids = set(costcenter_ids).intersection(costcenters_working.ids)
            if working_and_firing_costcenter_ids:
                working_and_firing_costcenters = self.env['ab_costcenter'].browse(
                    list(working_and_firing_costcenter_ids))
                cc_table = ""
                for cc in working_and_firing_costcenters:
                    cc_table += f"{cc.code}\t{cc.name}\n"
                raise ValidationError(_("You try to set firing for working employees!\n"
                                        f"{cc_table}"))

        balances_groups = self._get_balances_group(domain)
        je_list = []
        for costcenter in balances_groups:
            costcenter_id = costcenter[0]
            costcenter_deductions = list(costcenter[1])
            total_net_val = sum(v['total_net_val'] for v in costcenter_deductions)
            costcenter_lines = []
            due_line_index = None
            if not float_is_zero(total_net_val, precision_rounding=precision):
                debit_val = total_net_val > 0 and total_net_val or 0
                credit_val = total_net_val < 0 and total_net_val * -1 or 0
                debit_val = float_round(debit_val, precision_rounding=precision)
                credit_val = float_round(credit_val, precision_rounding=precision)
                if not (float_is_zero(debit_val, precision_rounding=precision) and
                        float_is_zero(credit_val, precision_rounding=precision)):
                    costcenter_lines.append({
                        'due_date': due_date,
                        'explain': explain,
                        'store_id': store_id,
                        'account_id': due_salaries_account_id,
                        'costcenter_id': costcenter_id,
                        'debit_val': debit_val,
                        'credit_val': credit_val,
                    })
                    due_line_index = len(costcenter_lines) - 1

            for je in costcenter_deductions:
                total_net_val = je.get('total_net_val')
                if float_is_zero(total_net_val, precision_rounding=precision):
                    continue

                account_id = je.get('account_id')[0]
                credit_val = total_net_val > 0 and total_net_val or 0
                debit_val = total_net_val < 0 and total_net_val * -1 or 0
                debit_val = float_round(debit_val, precision_rounding=precision)
                credit_val = float_round(credit_val, precision_rounding=precision)
                if (float_is_zero(debit_val, precision_rounding=precision) and
                        float_is_zero(credit_val, precision_rounding=precision)):
                    continue

                costcenter_lines.append({
                    'due_date': due_date,
                    'explain': explain,
                    'store_id': store_id,
                    'account_id': account_id,
                    'costcenter_id': costcenter_id,
                    'debit_val': debit_val,
                    'credit_val': credit_val,
                })
            if costcenter_lines:
                total_debit = sum(l['debit_val'] for l in costcenter_lines)
                total_credit = sum(l['credit_val'] for l in costcenter_lines)
                diff = float_round(total_debit - total_credit, precision_rounding=precision)
                if not float_is_zero(diff, precision_rounding=precision):
                    adjust_index = due_line_index
                    if adjust_index is None:
                        if diff > 0:
                            debit_indices = [i for i, l in enumerate(costcenter_lines) if l['debit_val'] > 0]
                            adjust_index = max(debit_indices, key=lambda i: costcenter_lines[i]['debit_val'])
                        else:
                            credit_indices = [i for i, l in enumerate(costcenter_lines) if l['credit_val'] > 0]
                            adjust_index = max(credit_indices, key=lambda i: costcenter_lines[i]['credit_val'])

                    line = costcenter_lines[adjust_index]
                    if diff > 0:
                        if line['debit_val'] > 0:
                            line['debit_val'] = float_round(line['debit_val'] - diff, precision_rounding=precision)
                        else:
                            line['credit_val'] = float_round(line['credit_val'] + diff, precision_rounding=precision)
                    else:
                        diff = -diff
                        if line['credit_val'] > 0:
                            line['credit_val'] = float_round(line['credit_val'] - diff, precision_rounding=precision)
                        else:
                            line['debit_val'] = float_round(line['debit_val'] + diff, precision_rounding=precision)
                    costcenter_lines[adjust_index] = line

                je_list.extend(costcenter_lines)
        if je_type == 'deduction':
            self.add_costcenters_to_month_prevented_deductions(costcenter_ids, last_day_of_month(due_date))
        elif je_type == 'firing':
            self.add_costcenters_to_forbidden_deductions(costcenter_ids)

        if je_list:
            self._write_je_list(header_je, je_list)
            header_je.sudo_confirm_all_je()

    ###############################################################################
    def _write_je_list(self, header_je, je_list):
        header_je = header_je.with_context(sudo_confirm=True)
        return header_je.write({"line_ids": [(0, 0, d) for d in je_list],
                                "is_posted": True,
                                "allowed_negative": True})

    ###############################################################################
    def _create_payment_for_bank(self):
        costcenter_codes_list = self.costcenter_codes.strip().split('\n')
        costcenter_ids = self.env['ab_costcenter'].search([('code', 'in', costcenter_codes_list)]).ids
        self._validate_deductions_is_done(costcenter_ids)
        due_salaries_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries').id

        domain = [
            ('account_id', '=', due_salaries_account_id),
            ('costcenter_id', 'in', costcenter_ids),
        ]

        balances_groups = self._get_balances_group(domain)

        due_date = self.due_month.replace(day=1)
        explain = _("Auto JE Due Salaries")
        store_id = 78
        due_salaries_account_id = due_salaries_account_id
        costcenter_admin_id = self.env['ab_costcenter'].search([('code', '=', '1')]).id
        je_list = []
        for costcenter in balances_groups:
            costcenter_id = costcenter[0]
            costcenter_due_salaries_list = list(costcenter[1])
            total_net_val = sum(v['total_net_val'] for v in costcenter_due_salaries_list)
            credit_val = total_net_val > 0 and total_net_val or 0
            debit_val = total_net_val < 0 and total_net_val * -1 or 0
            if debit_val < 1:
                continue
            je_list.append({
                'due_date': due_date,
                'explain': explain,
                'store_id': store_id,
                'account_id': due_salaries_account_id,
                'costcenter_id': costcenter_id,
                'debit_val': debit_val,
                'credit_val': credit_val,
            })

        net_val = sum(d['debit_val'] - d['credit_val'] for d in je_list if d['account_id'] == due_salaries_account_id)
        credit_val = net_val > 0 and net_val or 0
        debit_val = net_val < 0 and net_val * -1 or 0
        header_je = {
            'due_date': due_date,
            'explain': explain,
            'store_id': store_id,
            'account_id': due_salaries_account_id,
            'costcenter_id': costcenter_admin_id,
            'debit_val': debit_val,
            'credit_val': credit_val,
        }
        self.write({"line_ids": [(0, 0, header_je)] + [(0, 0, d) for d in je_list]})

    def _create_payment_for_cash(self):
        due_salaries_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries').id

        costcenter_codes_list = self.costcenter_codes.strip().split('\n')
        costcenter_ids = self.env['ab_costcenter'].search([('code', 'in', costcenter_codes_list)]).ids
        self._validate_deductions_is_done(costcenter_ids)

        domain = [
            ('account_id', '=', due_salaries_account_id),
            ('costcenter_id', 'in', costcenter_ids),
        ]

        balances_groups = self._get_balances_group(domain)

        due_date = self.due_month.replace(day=1)
        explain = _("Auto JE Due Salaries")
        store_id = 78
        due_salaries_account_id = due_salaries_account_id
        je_list = []
        due_salaries_cash_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries_cash').id
        for costcenter in balances_groups:
            costcenter_id = costcenter[0]
            costcenter_due_salaries_list = list(costcenter[1])
            total_net_val = sum(v['total_net_val'] for v in costcenter_due_salaries_list)
            credit_val = total_net_val > 0 and total_net_val or 0
            debit_val = total_net_val < 0 and total_net_val * -1 or 0
            if debit_val < 1:
                continue
            je_list.append({
                'due_date': due_date,
                'explain': explain,
                'store_id': store_id,
                'account_id': due_salaries_account_id,
                'costcenter_id': costcenter_id,
                'debit_val': debit_val,
                'credit_val': credit_val,
            })
            je_list.append({
                'due_date': due_date,
                'explain': explain,
                'store_id': store_id,
                'account_id': due_salaries_cash_account_id,
                'costcenter_id': costcenter_id,
                'debit_val': credit_val,
                'credit_val': debit_val,
            })

        self.write({"line_ids": [(0, 0, d) for d in je_list]})

    def btn_remove_all_je(self):
        self.write({"line_ids": [(5,)]})

    def add_costcenters_to_month_prevented_deductions(self, costcenter_ids, till_month):
        self.env['ab_due_salaries_wizard'].add_month_prevented_ids(costcenter_ids, till_month)

    def add_costcenters_to_forbidden_deductions(self, costcenter_ids):
        self.env['ab_due_salaries_wizard'].add_forbidden_ids(costcenter_ids)

    def _validate_deductions_is_done(self, costcenter_ids):
        firing_parent_account_id = self.env.ref('ab_accounting.ab_accounting_account_guide_firing_parent').id

        costcenters_working = self.env['ab_hr_employee'].search([('internal_working_employee', '=', True)]).mapped(
            'costcenter_id')
        costcenters_working_set = set(costcenters_working.ids)

        salary_month = self._calc_salary_month()
        deduction_domain = [
            ('costcenter_id', 'in', costcenter_ids),
            ('due_date', '<=', last_day_of_month(salary_month)),
            ('account_id.salary_deduction', '=', True)
        ]

        firing_domain = [
            ('costcenter_id', 'in', costcenter_ids),
            ('account_id.parent_id', '=', firing_parent_account_id)]

        deduction_je_list = self._get_je_list(domain=deduction_domain)
        firing_je_list = self._get_je_list(domain=firing_domain)
        for cc_id in costcenter_ids:
            # je_type supposed to be deduction
            if cc_id in costcenters_working_set:
                if cc_id in {d['costcenter_id'] for d in deduction_je_list}:
                    raise ValidationError(_(f"There is current month deduction not computed,\n"
                                            "please make deduction action for costcenter:\n"
                                            f"{self.env['ab_costcenter'].browse(cc_id).name}"
                                            ))
            else:
                if cc_id in {d['costcenter_id'] for d in firing_je_list}:
                    raise ValidationError(_(f"There is a deduction not computed,\n"
                                            "please make firing action for costcenter:\n"
                                            f"{self.env['ab_costcenter'].browse(cc_id).name}"
                                            ))

    def _get_je_list(self, domain):

        balances_groups = self._get_balances_group(domain)
        je_list = []
        for costcenter in balances_groups:
            costcenter_id = costcenter[0]
            costcenter_balances = list(costcenter[1])
            for je in costcenter_balances:
                total_net_val = je.get('total_net_val')
                if abs(total_net_val) < 0.5:
                    continue

                account_id = je.get('account_id')[0]
                credit_val = total_net_val > 0 and total_net_val or 0
                debit_val = total_net_val < 0 and total_net_val * -1 or 0

                je_list.append({
                    'account_id': account_id,
                    'costcenter_id': costcenter_id,
                    'debit_val': debit_val,
                    'credit_val': credit_val,
                })
        return je_list

    def _get_balances_group(self, domain):
        balances_list = self.env['ab_accounting_je_line_qry'].sudo().read_group(
            domain=domain,
            fields=['account_id', 'costcenter_id', 'total_net_val:sum(net_val)'],
            groupby=['account_id', 'costcenter_id', ],
            orderby='costcenter_id',
            lazy=False
        )
        return itertools.groupby(balances_list, key=lambda x: x['costcenter_id'][0])
