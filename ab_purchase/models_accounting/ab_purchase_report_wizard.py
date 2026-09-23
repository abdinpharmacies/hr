from collections import defaultdict
from time import perf_counter

from odoo import api, fields, models, _
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta


def get_termination_date(entry_date, termination_day):
    # Check if entry day is greater than termination day
    if entry_date.day <= termination_day:
        # "termination_day/currentMonth"
        termination_date = entry_date + relativedelta(day=termination_day)
    else:
        # "termination_day/nextMonth"
        termination_date = entry_date + relativedelta(months=1, day=termination_day)

    return termination_date


class AbPurchaseReportWizard(models.TransientModel):
    _name = 'ab_purchase_report_wizard'
    _description = 'ab_purchase_report_wizard'

    name = fields.Char()
    html = fields.Html(readonly=True)

    def btn_export_excel_account_statement(self):
        action = self.env.ref('ab_purchase.action_ab_supplier_balances_excel')
        action[0].name = "Supplier Balances"
        return action.report_action(self)

    def btn_print_pdf_account_statement(self):
        action = self.env.ref('ab_purchase.action_print_supplier_balances_pdf')
        data = self.get_je_data()
        return action.report_action(self, data=data)

    def btn_browse_account_statement(self):
        data = self.get_je_data()
        if data['moves_count'] > 200:
            data['rows'] = data['rows'][0:200]
            data['rows_count_warning'] = _(f"Report has {data['moves_count']}, Only 200 lines can be shown.")
        html = self.env.ref('ab_purchase.balance_dist')._render(data)
        self.write({'html': html})

    def get_je_data(self):
        start = perf_counter()
        supplier_account = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers')
        due_supplier_account = self.env['ab_accounting_account_guide'].browse(486)
        supplier_account_id = supplier_account.id
        due_supplier_account_id = due_supplier_account.id
        today = date.today()

        je_mo = self.env['ab_accounting_je_line'].sudo()
        bracket_mo = self.env['ab_supplier_bracket']
        credit_suppliers_ids = bracket_mo.search([('credit_days', '>', 0)]).mapped('supplier_id.id')
        supp_balance_map = defaultdict(float)
        bracket_map = defaultdict(lambda: bracket_mo)
        brackets = bracket_mo.search([('credit_days', '>', 0)], order='credit_days desc')
        for bracket in brackets:
            # get the first (greatest as order='credit_days desc') bracket.credit_days
            if not bracket_map[bracket.supplier_id.id]:
                bracket_map[bracket.supplier_id.id] = bracket
        # je_lines_has_claim = je_mo.search([
        #     ('account_id', '=', supplier_account_id),
        #     ('is_posted', '=', True),
        #     ('claim_id', '!=', False),
        #     ('claim_id.total_claim', '<', 10),
        #     ('claim_id.total_claim', '>', 10),
        # ], order='due_date DESC')

        claim_balanced = self.env['ab_purchase_claim'].sudo().search([
            ('total_claim', '<', 10), ('total_claim', '>', -10)
        ])
        je_lines_no_claim = je_mo.search([
            ('account_id', '=', supplier_account_id),
            ('is_posted', '=', True),
            ('claim_id', 'not in', claim_balanced.ids),
            ('costcenter_id', 'in', credit_suppliers_ids),
        ], order='due_date DESC')

        for je in self.web_progress_iter(je_lines_no_claim, 'looping ...'):
            costcenter_id = je.costcenter_id.id
            je_due_date = je.due_date
            account_name = je.account_id.name
            credit_days = bracket_map[costcenter_id].credit_days
            if credit_days:
                entry_date = je_due_date
                termination_day = bracket_map[costcenter_id].termination_day
                termination_date = get_termination_date(entry_date, termination_day)
                due_date = termination_date + timedelta(days=credit_days)
            else:
                due_date = today
                termination_date = due_date

            if due_date and due_date >= today:
                supp_balance_map[(costcenter_id, termination_date, due_date, account_name)] += je.net_val
            else:
                supp_balance_map[(costcenter_id, today, today, account_name)] += je.net_val

        headers = ["Cost Center Code", "Account", "Cost Center Name",
                   'Termination Date', 'Credit Days', "Due Date", "Total Value"]
        rows = []
        for key, val in supp_balance_map.items():
            costcenter_id = key[0]
            termination_date = key[1]
            due_date = key[2]
            account_name = key[3]

            bracket = bracket_map[costcenter_id]
            credit_days = bracket.credit_days
            costcenter = bracket.supplier_id
            cc_code = costcenter.code
            cc_name = costcenter.name
            if abs(val) > 100:
                rows.append([cc_code, account_name, cc_name,
                             termination_date, credit_days, due_date,
                             val])

        cr = self._cr
        credit_suppliers_str = ','.join(map(str, credit_suppliers_ids))
        if credit_suppliers_str:
            cr.execute(f"""
            SELECT cc.code,cc.name,sum(net_val),acc.name,CURRENT_DATE
                FROM ab_accounting_je_line je
                JOIN ab_accounting_je_header jeh on jeh.id = je.header_id
                JOIN ab_costcenter cc on je.costcenter_id=cc.id
                JOIN ab_accounting_account_guide acc on je.account_id=acc.id
                WHERE je.active=True and jeh.is_posted=True and je.account_id = {supplier_account_id} 
                and je.costcenter_id is not null
                and je.costcenter_id not in ({credit_suppliers_str})
                group by cc.code,cc.name,acc.name
            UNION ALL 
            SELECT cc.code,cc.name,sum(net_val),acc.name,max(due_date) 
                FROM ab_accounting_je_line je
                JOIN ab_costcenter cc on je.costcenter_id=cc.id
                JOIN ab_accounting_account_guide acc on je.account_id=acc.id
                WHERE je.active=True and je.account_id = {due_supplier_account_id} 
                and je.costcenter_id is not null
                group by cc.code,cc.name,acc.name
            """)

            data = self._cr.fetchall()
            for row in data:
                cc_code = row[0]
                cc_name = row[1]
                val = row[2]
                account_name = row[3]
                due_date = row[4]
                credit_days = 0
                termination_date = due_date
                if abs(val) > 100:
                    rows.append([cc_code, account_name, cc_name,
                                 termination_date, credit_days, due_date,
                                 val])

        rows.sort(key=lambda x: x[-2], reverse=True)
        return {
            'description': 'Report Name',
            'start_balance': 0,
            'end_balance': 0,
            'start_date': today,
            'end_date': today,
            'headers': headers,
            'rows': rows,
            'moves_count': len(rows),
        }
    # def get_je_data(self):
    #     start = perf_counter()
    #     supplier_account = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers')
    #     due_supplier_account = self.env['ab_accounting_account_guide'].browse(486)
    #     supplier_account_id = supplier_account.id
    #     due_supplier_account_id = due_supplier_account.id
    #     today = date.today()
    #
    #     je_mo = self.env['ab_accounting_je_line'].sudo()
    #     bracket_mo = self.env['ab_supplier_bracket']
    #     credit_suppliers_ids = bracket_mo.search([('credit_days', '>', 0)]).mapped('supplier_id.id')
    #     supp_balance_map = defaultdict(float)
    #     bracket_map = defaultdict(lambda: bracket_mo)
    #     brackets = bracket_mo.search([('credit_days', '>', 0)], order='credit_days desc')
    #     for bracket in brackets:
    #         # get the first (greatest as order='credit_days desc') bracket.credit_days
    #         if not bracket_map[bracket.supplier_id.id]:
    #             bracket_map[bracket.supplier_id.id] = bracket
    #     je_lines = je_mo.search([
    #         ('account_id', '=', supplier_account_id),
    #         ('is_posted', '=', True),
    #         ('costcenter_id', 'in', credit_suppliers_ids),
    #     ], order='due_date DESC')
    #
    #     for je in self.web_progress_iter(je_lines, 'looping ...'):
    #         costcenter_id = je.costcenter_id.id
    #         je_due_date = je.due_date
    #         account_name = je.account_id.name
    #         credit_days = bracket_map[costcenter_id].credit_days
    #         if credit_days:
    #             entry_date = je_due_date
    #             termination_day = bracket_map[costcenter_id].termination_day
    #             termination_date = get_termination_date(entry_date, termination_day)
    #             due_date = termination_date + timedelta(days=credit_days)
    #         else:
    #             due_date = today
    #             termination_date = due_date
    #
    #         if due_date and due_date >= today:
    #             supp_balance_map[(costcenter_id, termination_date, due_date, account_name)] += je.net_val
    #         else:
    #             supp_balance_map[(costcenter_id, today, today, account_name)] += je.net_val
    #
    #     headers = ["Cost Center Code", "Account", "Cost Center Name",
    #                'Termination Date', 'Credit Days', "Due Date", "Total Value"]
    #     rows = []
    #     for key, val in supp_balance_map.items():
    #         costcenter_id = key[0]
    #         termination_date = key[1]
    #         due_date = key[2]
    #         account_name = key[3]
    #
    #         bracket = bracket_map[costcenter_id]
    #         credit_days = bracket.credit_days
    #         costcenter = bracket.supplier_id
    #         cc_code = costcenter.code
    #         cc_name = costcenter.name
    #         if abs(val) > 100:
    #             rows.append([cc_code, account_name, cc_name,
    #                          termination_date, credit_days, due_date,
    #                          val])
    #
    #     cr = self._cr
    #     credit_suppliers_str = ','.join(map(str, credit_suppliers_ids))
    #     if credit_suppliers_str:
    #         cr.execute(f"""
    #         SELECT cc.code,cc.name,sum(net_val),acc.name,CURRENT_DATE
    #             FROM ab_accounting_je_line je
    #             JOIN ab_accounting_je_header jeh on jeh.id = je.header_id
    #             JOIN ab_costcenter cc on je.costcenter_id=cc.id
    #             JOIN ab_accounting_account_guide acc on je.account_id=acc.id
    #             WHERE je.active=True and jeh.is_posted=True and je.account_id = {supplier_account_id}
    #             and je.costcenter_id is not null
    #             and je.costcenter_id not in ({credit_suppliers_str})
    #             group by cc.code,cc.name,acc.name
    #         UNION ALL
    #         SELECT cc.code,cc.name,sum(net_val),acc.name,max(due_date)
    #             FROM ab_accounting_je_line je
    #             JOIN ab_costcenter cc on je.costcenter_id=cc.id
    #             JOIN ab_accounting_account_guide acc on je.account_id=acc.id
    #             WHERE je.active=True and je.account_id = {due_supplier_account_id}
    #             and je.costcenter_id is not null
    #             group by cc.code,cc.name,acc.name
    #         """)
    #
    #         data = self._cr.fetchall()
    #         for row in data:
    #             cc_code = row[0]
    #             cc_name = row[1]
    #             val = row[2]
    #             account_name = row[3]
    #             due_date = row[4]
    #             credit_days = 0
    #             termination_date = due_date
    #             if abs(val) > 100:
    #                 rows.append([cc_code, account_name, cc_name,
    #                              termination_date, credit_days, due_date,
    #                              val])
    #
    #     rows.sort(key=lambda x: x[-2], reverse=True)
    #     return {
    #         'description': 'Report Name',
    #         'start_balance': 0,
    #         'end_balance': 0,
    #         'start_date': today,
    #         'end_date': today,
    #         'headers': headers,
    #         'rows': rows,
    #         'moves_count': len(rows),
    #     }
