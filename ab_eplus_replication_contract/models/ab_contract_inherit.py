# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

EPLUS_SERVER_IP = config.get("bconnect_ip1")
EPLUS_CONTRACT_SQL = """
WITH x AS (
    SELECT
        CASE cp.cust_active WHEN 1 THEN 1 ELSE 0 END AS active,
        cp.cust_name_ar,
        cp.cust_code AS parent_code,

        c.cust_id AS child_cust_id,
        c.cust_code AS child_cust_code,
        c.cust_contract_id,

        cc.*,

        ROW_NUMBER() OVER (
            PARTITION BY cc.cc_id
            ORDER BY c.cust_id DESC   -- ← اختار مين؟ (غيّرها حسب منطقك)
        ) AS rn
    FROM Customer_Contracts cc
    LEFT JOIN Customer cp
        ON cp.cust_id = cc.cc_cust_id
    LEFT JOIN Customer c
        ON c.cust_parent = cp.cust_id
       AND c.cust_contract_id = cc.cc_id
    WHERE cp.cust_name_ar NOT LIKE '%عروض%'
)
SELECT *
FROM x
WHERE rn = 1; 
                     """


def _to_bool(value):
    if value is None:
        return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)


class AbContract(models.Model):
    _name = 'ab_contract'
    _inherit = ["ab_contract", "ab_eplus_connect"]

    @api.model
    def replicate_contracts_from_eplus(self, server=EPLUS_SERVER_IP, xrows=10000):
        _logger.info("Starting ePlus contract replication from %s", server)
        with self.connect_eplus(server=server, param_str="?") as conn:
            with conn.cursor(as_dict=True) as cr:
                cr.execute(EPLUS_CONTRACT_SQL)
                while True:
                    rows = cr.fetchall()
                    if not rows:
                        break
                    self._replicate_contract_rows(rows)
                    self.env.cr.commit()

        _logger.info("Completed ePlus contract replication")

    def _replicate_contract_rows(self, rows):
        for row in rows:
            values = self._prepare_contract_vals(row)
            eplus_serial = values.get("eplus_serial")
            if eplus_serial is None:
                continue

            existing = self.with_context(active_test=False).sudo().search(
                [("eplus_serial", "=", eplus_serial)],
                limit=1,
            )
            if existing:
                existing.with_context(eplus_replication=True).write(values)
            else:
                self.with_context(eplus_replication=True).create(values)

    @api.model
    def _prepare_contract_vals(self, row):
        last_update = row.get("sec_update_date") or row.get("sec_insert_date")
        cc_pay_perc_rule = row.get("cc_pay_perc_rule")
        odoo_cc_pay_perc_rule = 'company'
        if cc_pay_perc_rule == 0:
            odoo_cc_pay_perc_rule = 'person'
        elif cc_pay_perc_rule == 1:
            odoo_cc_pay_perc_rule = 'company'
        elif cc_pay_perc_rule == 2:
            odoo_cc_pay_perc_rule = 'all'


        return {
            "eplus_serial": row.get("cc_id"),
            "name": f"{row.get('cust_name_ar')} - {row.get('child_cust_code')} - {odoo_cc_pay_perc_rule} ({row.get("cc_pay_perc")} %)",
            "paid_percentage": row.get("cc_pay_perc"),
            "eplus_cust_code": row.get("child_cust_code"),
            "eplus_cust_id": row.get("child_cust_id"),
            "paid_amount": row.get("cc_pay_value"),
            "discount_percentage_rule": odoo_cc_pay_perc_rule,
            "max_bill_value": row.get("cc_max_bill_value"),
            "local_product_discount": row.get("cc_local_items_disc"),
            "imported_product_discount": row.get("cc_imported_items_disc"),
            "local_made_product_discount": row.get("cc_local_made_items_disc"),
            "special_import_product_discount": row.get("cc_special_import_items_disc"),
            "investment_product_discount": row.get("cc_investment_items_disc"),
            "other_product_discount": row.get("cc_other_items_disc"),
            "active": _to_bool(row.get("active")),
            "last_update_date": last_update,
            "eplus_create_date": row.get("sec_insert_date"),
        }
