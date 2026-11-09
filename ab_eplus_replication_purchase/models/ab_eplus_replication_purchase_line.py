from contextlib import nullcontext
from datetime import datetime

from odoo import models
from odoo.tools import ormcache

PARAM_STR = "%s"


def _get_item_discount(eplus_pur_price, eplus_tax_value, exact_tax_ratio):
    item_discount = 1 - (eplus_tax_value / (eplus_pur_price * exact_tax_ratio))
    return item_discount


class ReplicationPurchaseLine(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_purchase_line(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                   where_extra_and="", eplus_serials=None, **kw):

        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_purchase_line')

        purchase_line = self._get_purchase_line_from_bconnect(last_update_date, xrows, where_extra_and,
                                                              eplus_serials=eplus_serials)

        for i, chunk_of_purchase_line in enumerate(purchase_line, 1):
            msg = f"Replicating purchase line Part {i}"
            self._start_purchase_line_replication(chunk_of_purchase_line, msg=msg, update_target=update_target,
                                                  replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

        # always commit at last
        self.env.cr.commit()

    def _get_purchase_line_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += (" and h.bill_status='0' " + where_extra_and)
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.serial in ({serials_str}) "

        sql = f"""
        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
        SELECT main.pth_id as header_eplus_serial
                        ,main.itm_id as product_eplus_serial
                        ,main.exp_date as exp_date
                        ,main.qnty as qty
                        ,main.bonus as bonus
                        ,main.itm_sell as price
                        ,main.itm_pur_price as eplus_pur_price
                        ,main.itm_tax_price as eplus_tax_value
                        ,main.itm_extra_dis/100 as eplus_extra_disc_percent
                        ,main.serial as eplus_serial
                        ,((itm_pur_price*(100-itm_extra_dis)/100) +itm_tax_price) * qnty as eplus_line_cost
                        ,((itm_pur_price*(100-itm_extra_dis)/100)+itm_tax_price) *qnty 
                            + bonus * itm_tax_price as eplus_final_cost
                        ,main.sec_update_date as last_update_date
                       FROM pur_trans_d main
                       join pur_trans_h h on h.pth_id = main.pth_id 
                       {where_condition}
                       order by last_update_date,h.pth_id
                       """
        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_purchase_line_replication(self, invoices, msg="Replicating purchase lines", replicate_all=False, **kw):
        invoices.sort(key=lambda x: x['header_eplus_serial'])
        header_eplus_serial = 0
        purchase_header = None
        with nullcontext():  # Odoo 15 norecompute was already a no-op.
            for item in self.web_progress_iter(invoices, msg=msg):
                if header_eplus_serial != int(item['header_eplus_serial']):
                    purchase_header = self.get_purchase_header(eplus_serial=item['header_eplus_serial'])

                product = self.get_product(eplus_serial=item['product_eplus_serial'])

                item['disc_tax_no_effect_value'] = 0
                taxes = self.env.ref("ab_taxes.ab_tax_exempt")
                item['taxes_ids'] = [(6, 0, taxes.ids)]

                # self._update_item_dict(item)  # check other taxes and set it
                self._update_item_dict_taxes(item)  # update taxes

                purchase_line_dict = {
                    "eplus_serial": item['eplus_serial'],
                    "header_id": purchase_header.id,
                    "product_id": product.id,
                    "uom_id": product.unit_l_id.id,
                    "exp_date": item['exp_date'] and datetime.date(item['exp_date']),
                    "qty": item['qty'],
                    "disc_tax_no_effect_value": item['disc_tax_no_effect_value'],
                    "bonus": item['bonus'],
                    "purchase_price": round(item['eplus_pur_price'], 3),
                    "price": item['price'],
                    "extra_discount_percentage": item['eplus_extra_disc_percent'] * 100,
                    "taxes_ids": item['taxes_ids'],
                    "last_update_date": item['last_update_date'],
                }
                if replicate_all:
                    purchase_line_dict.pop('last_update_date', None)

                self._get_or_create_record(purchase_line_dict, model_name='ab_purchase_line', **kw)

    def _update_item_dict_taxes(self, item):
        eplus_pur_price = float(item['eplus_pur_price'])
        eplus_extra_disc = float(item['eplus_extra_disc_percent'])
        eplus_tax_value = float(item['eplus_tax_value'])

        if eplus_pur_price and abs(eplus_tax_value / eplus_pur_price * 100) > 1:
            qty = float(item['qty'])
            eplus_line_cost = float(item['eplus_line_cost'])
            tax_ratio = eplus_tax_value / (eplus_pur_price * (1 - eplus_extra_disc))
            exact_tax_ratio, taxes = self._get_exact_taxes(tax_ratio)

            # do not change purchase price, instead add extra discount to item
            discount = _get_item_discount(eplus_pur_price, eplus_tax_value, exact_tax_ratio)

            #
            odoo_pur_after_disc = eplus_pur_price - eplus_pur_price * discount
            odoo_cost = (odoo_pur_after_disc + odoo_pur_after_disc * exact_tax_ratio) * qty

            item['eplus_extra_disc_percent'] = discount
            item['disc_tax_no_effect_value'] = odoo_cost - eplus_line_cost
            item['taxes_ids'] = [(6, 0, taxes.ids)]

    def get_purchase_line(self, eplus_serial):
        return self._get_or_replicate_record(model_name='ab_purchase_line', eplus_serial=eplus_serial)

    @ormcache('tax_pur_ratio')
    def _get_exact_taxes(self, tax_pur_ratio):
        if 0.230 <= tax_pur_ratio <= 0.232:
            # 14% + 8% =  23.12%
            return 0.2312, (self.env.ref("ab_taxes.ab_tax_14") | self.env.ref("ab_taxes.ab_tax_schedule_8"))
        if 0.196 <= tax_pur_ratio <= 0.198:
            # 14% + 5% = 19.7%
            return 0.197, (self.env.ref("ab_taxes.ab_tax_14") | self.env.ref("ab_taxes.ab_tax_schedule_5"))
        if 0.139 <= tax_pur_ratio <= 0.141:
            # 14%
            return 0.14, (self.env.ref("ab_taxes.ab_tax_14"))
        if 0.079 <= tax_pur_ratio <= 0.081:
            # 8%
            return 0.08, (self.env.ref("ab_taxes.ab_tax_schedule_8"))
        if 0.049 <= tax_pur_ratio <= 0.051:
            # 5%
            return 0.05, (self.env.ref("ab_taxes.ab_tax_schedule_5"))
        if -0.001 <= tax_pur_ratio <= 0.001:
            # 0%
            return 0.0, (self.env.ref("ab_taxes.ab_tax_exempt"))

        return 0.14, (self.env.ref("ab_taxes.ab_tax_14"))

    def _get_wrong_purchase_headers(self):
        pur_mo = self.env['ab_purchase_header'].sudo()
        # pur_line_mo = self.env['ab_purchase_line'].sudo()
        pur_h_eplus_serials = []
        for pur in self.web_progress_iter(pur_mo.search([('net_invoice_eq_total_cost', '=', False)]),
                                          msg='Looping Purchases ...'):
            if abs(pur.total_cost - pur.net_invoice) >= 2:
                pur_h_eplus_serials.append(pur.eplus_serial)
            else:
                pur_mo.search([('eplus_serial', '=', pur.eplus_serial)]).write({'net_invoice_eq_total_cost': True})
        return ','.join(map(str, pur_h_eplus_serials))

    def replicate_ab_purchase_line_missing(self):
        eplus_serials_str = self._get_wrong_purchase_headers()
        if eplus_serials_str:
            extra_where = f" and main.pth_id in ({eplus_serials_str})"
            self.replicate_ab_purchase_line(replicate_all=True, where_extra_and=extra_where, xrows=100, commit=True)
            self.replicate_ab_purchase_header(replicate_all=True, where_extra_and=extra_where, xrows=100, commit=True)

    # ab_purchase_header has two taxes 14+8  id=6068
