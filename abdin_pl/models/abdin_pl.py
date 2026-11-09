# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
import datetime
import time


class ClsUserAuth(models.Model):
    _inherit = 'res.users'

    pl_branch_ids = fields.Many2many(comodel_name="ab_store",
                                     relation="ab_store_res_users_rel",
                                     column1="user_id",
                                     column2="store_id",
                                     string="PL Branch Auth", )


class ClsSalesJE(models.Model):
    _name = 'abdin_pl.pl_temp'
    _description = 'View JE and sales Inquery'
    _order = 'analytic_level1'
    # _auto = False

    grand_level = fields.Char()
    analytic_level1 = fields.Char()
    analytic_level2 = fields.Char()
    final_account = fields.Char()
    net_val = fields.Float()
    due_date = fields.Date()
    branch = fields.Char()
    with_account = fields.Char()
    explain = fields.Text()
    data_source = fields.Selection([('eplus', 'ePlus'), ('je', 'JE'), ], index=True)

    # @api.model
    # def fields_view_get(self, view_id=None, view_type='list', toolbar=False, submenu=False):
    #     ret_val = super(ClsSalesJE, self).fields_view_get(
    #         view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
    #
    #     return ret_val

    def reset_pl(self):
        cr = self.env.cr
        cr.execute("TRUNCATE ONLY abdin_pl_pl_temp RESTART IDENTITY;")
        self.get_pl_net()

    ########################################################################
    def get_pl_net(self):

        cr = self.env.cr

        # Reinsert JEs
        sql = '\n'.join([
            self.delete_abdin_je(),
            self.insert_abdin_je(),
        ])
        cr.execute(sql)

        # Reinsert ePlus Sales
        has_eplus_sales = self.env['abdin_pl.pl_temp'].search([('data_source', '=', 'eplus')], limit=1)
        if not (has_eplus_sales and has_eplus_sales[0]):
            sql = '\n'.join([
                self.drop_eplus_sales(),
                self.create_eplus_sales(),
                self.insert_sales(),
            ])
            cr.execute(sql)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload', }

    ########################################################################
    @staticmethod
    def drop_eplus_sales():
        return "DROP Table IF EXISTS abdin_eplus_sales_concl_temp;"

    ########################################################################
    @staticmethod
    def delete_abdin_je():
        return "DELETE FROM abdin_pl_pl_temp WHERE data_source='je';"

    ########################################################################
    @staticmethod
    def insert_abdin_je():
        return """
               INSERT INTO abdin_pl_pl_temp(grand_level, analytic_level1, analytic_level2, final_account, branch,
                                            due_date,
                                            net_val, explain, data_source)
               SELECT CASE
                          WHEN g1.internal_group = 'expense' THEN 'المصروفات'
                          WHEN g1.internal_group = 'income' THEN 'الايرادات'
                          ELSE 'Error'
                          END,
                      g_parent.name,
                      g_parent.name,
                      g1.name,
                      CASE
                          WHEN bp.name LIKE 'فرع %' THEN bp.name
                          WHEN b.name NOT LIKE 'فرع %' THEN 'الادارة العامة'
                          ELSE b.name
                          END,
                      j.due_date,
                      (j.debit_val - j.credit_val) * -1,
                      j.explain,
                      'je'
               FROM ab_accounting_je_line AS j
                        LEFT JOIN ab_accounting_account_guide AS g1
                                  ON j.account_id = g1.id
                        LEFT JOIN ab_accounting_account_guide AS g_parent
                                  ON g1.parent_id = g_parent.id
                        LEFT JOIN ab_store AS b
                                  ON j.store_id = b.id
                        LEFT JOIN ab_store AS bp
                                  ON b.parent_id = bp.id
               WHERE j.due_date >= '2023/01/01'
                 AND g1.internal_group IN ('expense', 'income')
                 AND j.active = True
               ;
               """

    ########################################################################
    @staticmethod
    def create_eplus_sales():
        return """

               CREATE
               TEMP TABLE abdin_eplus_sales_concl_temp AS(
            SELECT
            date_trunc('month',s.sec_insert_date_h+interval '2 hour') as due_date,
            sto.sto_name_ar as branch,
            bill_type ,
            round(
                sum(
                    CASE 
                        WHEN bill_type = '2' 
                            THEN s.total_sales_h - s.credit_value_contract
                        ELSE s.total_sales_h
                    END
                )
            ) AS total_sale,
            round(sum(s.total_sales_h-s.total_bill_after_disc_h)) as sales_discounts,
            
            round(
                sum(
                    CASE 
                        WHEN bill_type = '2' AND s.total_sales_h <> 0
                            THEN s.cost_d * (s.loaded_value_contract/s.total_sales_h)
                        ELSE s.cost_d
                    END
                )
            ) AS sales_cost,

            round(sum(s.credit_value_contract)) as credit_contract_sales,
            round(sum(s.loaded_value_contract)) as cash_contract_sales,
            CASE
                WHEN s.credit_value_contract>0 THEN True
                ELSE False
            END
            AS is_contract,
            'eplus' as data_source

            FROM abdin_eplus_r_sales_trans_h as s
            left join abdin_eplus_store as sto on s.sto_id=sto.id
            where s.sec_insert_date_h > '2023-01-01'
            Group by sto.sto_name_ar,
            bill_type,
            date_trunc('month',s.sec_insert_date_h+interval '2 hour'),
            CASE
                WHEN s.credit_value_contract>0 THEN True
                ELSE False
            END
        ); \
               """

    ########################################################################
    @staticmethod
    def insert_sales():
        sales_sql = ""
        bill_types = [('1', '1-مجمل الربح كاش'),
                      ('2', '2-مجمل الربح عروض شركات'),
                      ('3', '3-مجمل الربح تعاقدات عملاء')]
        income_types = [('total_sale', '1-المبيعات'),
                        ('sales_discounts * -1', '2-الخصم'),
                        ('sales_cost * -1', '3-التكلفة')]
        for bill_type in bill_types:
            for income_type in income_types:
                sales_sql += f"""
                INSERT INTO abdin_pl_pl_temp(
                    grand_level,
                    analytic_level1, 
                    analytic_level2, 
                    due_date, 
                    branch, 
                    net_val, 
                    data_source)
                    select 'الايرادات', 
                        '{bill_type[1]}',
                        '{income_type[1]}',
                        due_date,
                        branch,
                        {income_type[0]}, 
                        data_source
                    from abdin_eplus_sales_concl_temp
                    where bill_type='{bill_type[0]}';
                """

        return sales_sql
