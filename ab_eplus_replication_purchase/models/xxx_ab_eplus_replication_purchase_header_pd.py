from time import perf_counter

import pandas as pd
from odoo import models

PARAM_STR = "%s"


class ReplicationPurchase(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_purchase_header(self, replicate_all=False, update_target=None, xrows=10000):
        start = perf_counter()
        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_purchase_header')

        dfs = self._yield_purchase_dfs(last_update_date, xrows)

        for i, df in enumerate(dfs, 1):
            msg = f"Replicating purchase Part {i}"
            self._start_replicate_purchases(df, msg=msg, update_target=update_target)
            self.env.cr.commit()
        end = perf_counter()
        # print(f"New way - df - takes .................: {end - start}")

    def _yield_purchase_dfs(self, last_update_date, xrows):
        where_condition = self._get_where_condition(last_update_date)
        # #### FOR TESTING #####
        where_condition += (" and main.sec_insert_date between '2024-01-01' and '2024-01-01' "
                            " and main.bill_status='0' ")
        sql = f"""
                select main.pth_id as eplus_serial,
                       main.ven_bill_no as doc_code,
                       main.sto_id as store_eplus_serial,
                       main.ven_id as supplier_eplus_serial,
                       main.pth_notice as description,
                       -- ((main.total_dis_per/100)*main.total_bill+main.total_des_mon) as total_extra_discount,
                       main.ven_bill_date as doc_date,
                       (main.total_bill-(main.total_dis_per/100)*main.total_bill-main.total_des_mon) as net_invoice,
                       sum(d.qnty * d.itm_tax_price + d.bonus * d.itm_tax_price) as net_tax,
                       IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date
                       from pur_trans_h main
                       join pur_trans_d d on d.pth_id = main.pth_id
                       {where_condition}
                       group by main.pth_id,main.ven_bill_no,main.sto_id,main.ven_id,main.pth_notice,main.
                                ven_bill_date,main.total_bill,main.total_dis_per,main.total_des_mon,
                                main.sec_update_date, main.sec_insert_date
                       order by last_update_date
                       """
        with self.connect_eplus(param_str=PARAM_STR) as conn:
            params = (last_update_date,) if last_update_date else None
            dfs = pd.read_sql_query(sql, conn, chunksize=xrows, params=params)
            for df in dfs:
                yield df

    def _start_replicate_purchases(self, df, update_target, msg="Replicating purchases...", ):

        invoices = pd.DataFrame()
        invoices[['store_id', 'supplier_id']] = df[['store_eplus_serial', 'supplier_eplus_serial']].apply({
            'store_eplus_serial': lambda x: self.get_store(x).id,
            'supplier_eplus_serial': lambda x: self.get_supplier(x).id,
        })

        rest_of_cols = ['eplus_serial', 'doc_code',
                        'description', 'doc_date',
                        'net_invoice', 'net_tax',
                        'last_update_date']

        invoices[rest_of_cols] = df[rest_of_cols]

        invoices_list = invoices.to_dict('records')
        for inv in self.web_progress_iter(invoices_list, msg=msg):
            self._get_or_create_record(inv, model_name='ab_purchase_header', update_target=update_target)

    def get_purchase_header(self, eplus_serial):
        return self._get_or_replicate_record(model_name='ab_purchase_header', eplus_serial=eplus_serial)
