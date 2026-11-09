from time import perf_counter

from odoo import models

PARAM_STR = "%s"


class ReplicationPurchase(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_purchase_header(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                     where_extra_and="", eplus_serials=None, **kw):

        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_purchase_header')
        purchase = self._get_purchase_from_bconnect(last_update_date, xrows, where_extra_and,
                                                    eplus_serials=eplus_serials)
        for i, chunk_of_purchase in enumerate(purchase, 1):
            msg = f"Replicating purchase Part {i}"
            self._start_purchase_replication(chunk_of_purchase, msg=msg, update_target=update_target,
                                             replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

        # always commit at last
        self.env.cr.commit()

    def _get_purchase_from_bconnect(self, last_update_date, xrows, where_extra_and, eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += (" and main.bill_status='0' " + where_extra_and)
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.pth_id in ({serials_str}) "

        sql = f"""
                SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                select main.pth_id as eplus_serial,
                       main.ven_bill_no as doc_code,
                       main.sto_id as store_eplus_serial,
                       main.ven_id as supplier_eplus_serial,
                       main.pth_notice as description,
                       -- ((main.total_dis_per/100)*main.total_bill+main.total_des_mon) as total_extra_discount,
                       main.ven_bill_date as doc_date,
                       main.total_des_mon as eplus_total_disc_on_inv,
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
        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_purchase_replication(self, invoices, msg="Replicating purchase headers", replicate_all=False, **kw):
        for item in self.web_progress_iter(invoices, msg=msg):
            purchase_dict = {
                "eplus_serial": item['eplus_serial'],
                "doc_code": '-'.join(str(item['doc_code']).split()),
                "description": item['description'],
                "eplus_total_disc_on_inv": item['eplus_total_disc_on_inv'],
                "store_id": self.get_store(item['store_eplus_serial']).id,
                "supplier_id": self.get_supplier(item['supplier_eplus_serial']).id,
                # "total_extra_discount": item['total_extra_discount'],
                "doc_date": item['doc_date'],
                "net_invoice": item['net_invoice'],
                "net_tax": item['net_tax'],
                "last_update_date": item['last_update_date'],
            }
            if replicate_all:
                purchase_dict.pop('last_update_date', None)

            self._get_or_create_record(purchase_dict, model_name='ab_purchase_header', **kw)

    def get_actual_computed_diff(self):
        pur = self.env['ab_purchase_header'].search([])
        pur_list = []
        for rec in pur:
            total_cost = rec.total_cost
            net_invoice = rec.net_invoice
            eplus_serial = rec.eplus_serial
            total_tax = rec.total_tax
            net_tax = rec.net_tax
            if abs(total_cost - net_invoice) > 0.9:
                diff_line = (
                    rec.id,
                    eplus_serial,
                    f"line_count: {len(rec.line_ids)}",
                    f"total_cost: {total_cost}",
                    f"net_invoice: {net_invoice}",
                    f"total_tax: {total_tax}",
                    f"net_tax: {net_tax}",
                    f"diff: {total_cost - net_invoice}",
                )
                pur_list.append(diff_line)

    def get_purchase_header(self, eplus_serial, **kw):
        return self._get_or_replicate_record(model_name='ab_purchase_header', eplus_serial=eplus_serial, **kw)
