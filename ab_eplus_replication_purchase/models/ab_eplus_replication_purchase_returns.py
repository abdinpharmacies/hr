import os
from datetime import datetime, timedelta
from time import perf_counter
import pandas as pd

from odoo import models, fields
from odoo.exceptions import UserError

PARAM_STR = "%s"


def _get_item_discount(eplus_pur_price, eplus_tax_value):
    item_discount = 1 - (eplus_tax_value / (eplus_pur_price * 0.14))
    return item_discount


class AbPurchaseNoticeLine(models.Model):
    _name = 'ab_purchase_notice_line'
    _inherit = 'ab_purchase_notice_line'

    product_eplus_serial = fields.Integer(related='product_id.eplus_serial', string='Product ePlus Serial')


class ReplicationPurchaseLine(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_purchase_returns(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                   where_extra_and="", eplus_serials=None, **kw):

        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_purchase_notice_line')

        purchase_return_line = self._get_purchase_return_line_from_bconnect(last_update_date, xrows, where_extra_and,
                                                                            eplus_serials=eplus_serials)

        for i, chunk_of_purchase_return_line in enumerate(purchase_return_line, 1):
            msg = f"Replicating purchase return line Part {i}"
            self._start_purchase_returns_repl(chunk_of_purchase_return_line,
                                              msg=msg,
                                              update_target=update_target, replicate_all=False)

            if commit:
                self.env.cr.commit()

        # always commit at last
        self.env.cr.commit()

    def _get_purchase_return_line_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)

        where_condition += (" and h.bill_status='0' and  abs(h.total_bill- h.total_after_back)>1  " + where_extra_and)
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.serial in ({serials_str}) "

        sql = f"""
         SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
         SELECT main.pth_id as header_eplus_serial
                        ,main.serial as eplus_serial
                        ,h.sec_update_date as doc_date
                        ,main.itm_back_qty - main.itm_back_bonus as qty 
                        ,main.itm_back_bonus as bonus
                        ,h.ven_id as supplier_eplus_serial
                        ,main.sec_update_date as last_update_date
                       FROM pur_trans_d main
                       join pur_trans_h h on h.pth_id = main.pth_id 
                       {where_condition}
                       order by last_update_date,h.pth_id
                       """
        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_purchase_returns_repl(self, invoices, msg="Replicating purchase return lines", replicate_all=False,
                                     **kw):

        invoice_groups = pd.DataFrame(invoices).groupby(['header_eplus_serial', 'supplier_eplus_serial', 'doc_date'])

        for (header_eplus_serial, supplier_eplus_serial, doc_date), eplus_df in self.web_progress_iter(
                invoice_groups, msg=msg):
            purchase_header_id = self.get_purchase_header(header_eplus_serial)
            supplier_id = self.get_supplier(supplier_eplus_serial)

            lines = pd.DataFrame()
            lines['source_id'] = eplus_df['eplus_serial'].apply(lambda x: self.get_purchase_line(x).source_id.id)
            rest_of_columns = ['qty', 'bonus', 'eplus_serial']
            if not replicate_all:
                rest_of_columns.append('last_update_date')

            lines[rest_of_columns] = eplus_df[rest_of_columns]

            # return_lines to write
            return_lines = lines.to_dict('records')
            return_lines = self._get_actual_return_lines(return_lines)

            pur_return_model = self.env['ab_purchase_notice_header'].sudo()

            if return_lines:
                pur_return_model.create({
                    'supplier_id': supplier_id.id,
                    'doc_date': doc_date,
                    'purchase_header_id': purchase_header_id.id,
                    'line_ids': [(0, 0, line) for line in return_lines],
                })

    def _get_actual_return_lines(self, lines):
        """
        Create a new notice if found any changes in qty or bonus, and .
        """
        actual_return_lines = []
        for line in lines:
            eplus_serial = line['eplus_serial']
            qty = float(line['qty'])
            bonus = float(line['bonus'])
            pur_model = self.env['ab_purchase_notice_line'].sudo()
            record = pur_model.search([('eplus_serial', '=', eplus_serial)])
            if not record:
                if (qty + bonus) > 0:
                    actual_return_lines.append(line)
            else:
                values = {}
                if record.qty != qty:
                    values['qty'] = qty
                if record.bonus != bonus:
                    values['bonus'] = bonus
                if values:
                    record.update(values)

        return actual_return_lines

    def replicate_ab_purchase_confirm(self, xrows=10000, start_date=None, end_date=None, eplus_serials=None):
        self = self.with_user(2)
        extra_where = ""
        if eplus_serials:
            eplus_serials_str = ','.join(map(str, eplus_serials))
            extra_where += f" and  main.pth_id in ({eplus_serials_str}) and main.sec_insert_date > '2024-06-01' "
        else:
            if not start_date:
                start_date = datetime.today() - timedelta(days=15)
            if not end_date:
                end_date = datetime.today()

            if (end_date - start_date).days > 15:
                raise UserError("difference between end date and start date must be less than 15")
            if not ((end_date - start_date).days > 0):
                raise UserError("end date must be greater than start date")

            start_date = start_date.strftime('%Y-%m-%d')
            end_date = end_date.strftime('%Y-%m-%d')
            extra_where += (f" and  main.sec_insert_date between '{start_date}' and '{end_date}' "
                            " and main.sec_insert_date>'2024-06-01' ")

        self.replicate_ab_purchase_line(where_extra_and=extra_where, xrows=xrows, replicate_all=True)
        self.replicate_purchase_returns(where_extra_and=extra_where, xrows=xrows, replicate_all=True)
        self.submit_purchase_returns_in_inventory()
        self.env['ab_purchase_notice_header'].adjust_notice_jes(eplus_serials=eplus_serials)
