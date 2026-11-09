import datetime
from time import perf_counter
import pandas as pd

from odoo import models

PARAM_STR = "%s"


def _get_item_discount(eplus_pur_price, eplus_tax_value):
    item_discount = 1 - (eplus_tax_value / (eplus_pur_price * 0.14))
    return item_discount


class ReplicationPurchaseLine(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_purchase_g_returns(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                     where_extra_and=''
                                     ):
        last_update_date = None
        if not replicate_all:
            last_update_date = self.env['ab_purchase_notice_line'].sudo().with_context(active_test=False).search(
                [('last_update_date', '!=', False), ('eplus_serial_g_return', '!=', False)],
                order='last_update_date DESC',
                limit=1).last_update_date
            if last_update_date:
                last_update_date = last_update_date.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        purchase_return_line = self._get_purchase_g_return_line_from_bconnect(last_update_date, xrows, where_extra_and)

        for i, chunk_of_purchase_return_line in enumerate(purchase_return_line, 1):
            msg = f"Replicating purchase return line Part {i}"
            self._start_purchase_g_returns_repl(chunk_of_purchase_return_line,
                                                msg=msg,
                                                update_target=update_target)

            if commit:
                self.env.cr.commit()

        # always commit at last
        self.env.cr.commit()

    def _get_purchase_g_return_line_from_bconnect(self, last_update_date, xrows, where_extra_and):
        where_condition = self._get_where_condition(last_update_date)

        where_condition += (" " + where_extra_and)

        sql = f"""
        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
        SELECT h.ibh_id as eplus_g_header_serial
                        ,h.ibh_ven_id as supplier_eplus_serial 
                        ,h.sec_insert_date as doc_date
                        ,h.ibh_ven_back_conf as eplus_return_number
                        ,h.ibh_back_reason as eplus_is_exp
                        ,main.ibd_id as eplus_serial_g_return
                        ,main.ibd_itm_id as product_eplus_serial 
                        ,main.ibd_qty as qty 
                        ,main.ibd_pharm_price+main.ibd_tax_price as purchase_price 
                        ,0.0 as tax_price
                        ,IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date
                       FROM item_back_d main
                       join item_back_h h on h.ibh_id = main.ibd_ibh_id
                       {where_condition}
                       order by last_update_date,h.ibh_id
                       """
        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_purchase_g_returns_repl(self, invoices, msg="Replicating purchase return lines", **kw):

        start = perf_counter()

        invoice_groups = pd.DataFrame(invoices).groupby(
            ['eplus_g_header_serial', 'supplier_eplus_serial', 'doc_date', 'eplus_return_number', 'eplus_is_exp']
        )

        for grouper, eplus_df in self.web_progress_iter(invoice_groups, msg=msg):

            eplus_g_header_serial, supplier_eplus_serial, doc_date, eplus_return_number, eplus_is_exp = grouper

            supplier_id = self.get_supplier(supplier_eplus_serial)

            lines = pd.DataFrame()
            rest_of_columns = ['qty', 'eplus_serial_g_return', 'last_update_date']
            lines[rest_of_columns] = eplus_df[rest_of_columns]

            # @todo: find a better way to filter already_replicated lines
            already_replicated = self.env['ab_purchase_notice_line'].search([
                ('eplus_serial_g_return', '!=', False),
                # ('create_date', '>=', datetime.date.today() - datetime.timedelta(days=30)),
            ])
            already_replicated_serials = already_replicated.mapped('eplus_serial_g_return')

            # old lines to update
            old_lines = lines[lines['eplus_serial_g_return'].isin(already_replicated_serials)]

            # new_lines to create
            new_lines = lines[~lines['eplus_serial_g_return'].isin(already_replicated_serials)]

            # if no df for return then continue loop
            if new_lines.empty:
                continue

            # Create opening_balance header with store_id Cairo HQ
            o_b_header = self.env['ab_purchase_ob_header'].create({'store_id': 78})

            new_lines['source_id'] = eplus_df.apply(
                lambda row: self.create_source_id_for_g_return_line(
                    o_b_header.id,
                    row['product_eplus_serial'],
                    row['qty'],
                    row['purchase_price'],
                    row['tax_price'],
                ), axis=1)

            o_b_header.btn_submit_inventory()

            # return_lines to write
            return_lines = new_lines.to_dict('records')

            pur_return_model = self.env['ab_purchase_notice_header'].sudo()
            if return_lines:
                pur_return_model.create({
                    'supplier_id': supplier_id.id,
                    'eplus_g_header_serial': eplus_g_header_serial,
                    'doc_date': doc_date,
                    'doc_code': '-'.join(str(eplus_return_number).split()),
                    'line_ids': [(0, 0, line) for line in return_lines],
                })

        end = perf_counter()

    def create_source_id_for_g_return_line(self, o_b_header_id, product_eplus_serial, qty, purchase_price, tax_price):
        product = self.get_product(product_eplus_serial)
        taxes_id = self.env.ref('ab_taxes.ab_tax_14').id if tax_price else self.env.ref('ab_taxes.ab_tax_exempt').id
        o_b_line = self.env['ab_purchase_ob_line'].create({
            'header_id': o_b_header_id,
            'qty': qty,
            'product_id': product.id,
            'uom_id': product.unit_l_id.id,
            'purchase_price': purchase_price,
            'price': float(purchase_price) * 1.2,
            'taxes_ids': [(6, 0, [taxes_id])]
        })

        return o_b_line.source_id.id

    def update_g_return_headers_and_lines(self):
        lines_chunks = self._get_purchase_g_return_line_from_bconnect(
            None, 1000,
            where_extra_and=" and main.sec_insert_date>'2024-05-30'")
        pur_return_model = self.env['ab_purchase_notice_line'].sudo()

        for i, chunk in enumerate(lines_chunks, 1):
            for line in chunk:
                header = pur_return_model.search([('eplus_serial_g_return', '=', line['eplus_serial_g_return']),
                                                  ('header_id.eplus_g_header_serial', '=', False)
                                                  ], limit=1).header_id
                if header:
                    header.eplus_g_header_serial = line['eplus_g_header_serial']
