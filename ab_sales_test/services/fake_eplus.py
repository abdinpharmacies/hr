from collections import defaultdict

from odoo.tools.translate import _


class UnsupportedFakeEplusSQL(Exception):
    pass


def _norm_sql(sql):
    return " ".join(str(sql or "").lower().split())


class FakeEplusConnection:
    def __init__(self, scenario):
        self.scenario = scenario
        self.header = None
        self.header_updates = []
        self.lines = []
        self.delivery_ops = []
        self.stock_updates = []
        self.misc_ops = []
        self.committed = False
        self.rolled_back = False
        self.last_identity = 0
        self._inventory_select_count = defaultdict(int)
        self._product_rows = defaultdict(list)
        for line in scenario["lines"]:
            product_serial = int((line.get("source") or {}).get("itm_id") or 0)
            self._product_rows[product_serial].append(line)

    def cursor(self, as_dict=False):
        return FakeEplusCursor(self, as_dict=as_dict)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


class FakeEplusCursor:
    def __init__(self, connection, as_dict=False):
        self.connection = connection
        self.as_dict = as_dict
        self._result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def fetchone(self):
        if not self._result:
            return None
        row = self._result[0]
        self._result = self._result[1:]
        return row

    def fetchall(self):
        rows = self._result
        self._result = []
        return rows

    def execute(self, sql, params=None):
        params = tuple(params or ())
        normalized = _norm_sql(sql)

        if normalized.startswith("select top 1 sto_id, sto_name_ar from store"):
            source = self.connection.scenario["source"]
            self._set_rows([(source["sto_id"], "AB Sales Test Store")])
            return

        if "select itm_def_sell_price from item_catalog" in normalized:
            product_serial = int(params[0] or 0)
            line = self._first_product_row(product_serial)
            self._set_rows([(self._float((line.get("inputs") or {}).get("itm_sell")),)])
            return

        if "select cast(itm_unit1_unit3 as decimal" in normalized and "from item_catalog" in normalized:
            self._set_rows([(1.0,)])
            return

        if "from item_class_store ics" in normalized and "join item_catalog ic" in normalized:
            store_serial = int(params[0] or 0)
            product_serial = int(params[1] or 0)
            rows = self._inventory_rows_for_product(store_serial, product_serial)
            self._set_rows(rows)
            return

        if normalized.startswith("select top 1 sth_id from sales_trans_h"):
            self._set_rows([])
            return

        if normalized.startswith("insert into sales_trans_h"):
            self.connection.header = self._header_from_params(params)
            self.connection.last_identity = int((self.connection.scenario["source"] or {}).get("sth_id") or 0)
            if not self.connection.last_identity:
                self.connection.last_identity = 900000000 + len(self.connection.lines) + 1
            return

        if normalized.startswith("select cast(@@identity as bigint)"):
            self._set_rows([(self.connection.last_identity,)])
            return

        if normalized.startswith("select 1 from sales_trans_h"):
            self._set_rows([(1,)] if self.connection.header else [])
            return

        if normalized.startswith("insert into sales_trans_d"):
            self.connection.lines.append(self._line_from_params(params))
            return

        if normalized.startswith("update sales_trans_h set no_of_items"):
            self.connection.header_updates.append(("no_of_items", params))
            return

        if normalized.startswith("select total_bill from sales_trans_h"):
            total = (self.connection.header or {}).get("total_bill", 0.0)
            self._set_rows([(total,)])
            return

        if "select coalesce(sum(qnty * itm_sell), 0)" in normalized and "from sales_trans_d" in normalized:
            total = sum(
                self._float(line.get("qnty")) * self._float(line.get("itm_sell"))
                for line in self.connection.lines
            )
            self._set_rows([(total,)])
            return

        if "select cast(itm_qty as decimal(38,6)) from item_class_store" in normalized:
            self._set_rows([(999999.0,)])
            return

        if normalized.startswith("update item_class_store"):
            self.connection.stock_updates.append((sql, params))
            return

        if normalized.startswith("delete from sales_deliv_info"):
            self.connection.delivery_ops.append(("delete", params))
            return

        if normalized.startswith("insert into sales_deliv_info"):
            self.connection.delivery_ops.append(("insert", params))
            return

        if normalized.startswith("update sales_deliv_info set cust_id"):
            self.connection.delivery_ops.append(("update_cust_id", params))
            return

        if normalized.startswith("update sales_trans_h") and "fh_contract_id" in normalized:
            self.connection.header_updates.append(("contract", params))
            return

        if normalized.startswith("update sales_trans_h set cust_id"):
            self.connection.header_updates.append(("cust_id", params))
            return

        if normalized.startswith("update sales_trans_d") and "set col1" in normalized:
            self.connection.misc_ops.append(("promo_marker", params))
            return

        raise UnsupportedFakeEplusSQL(_("Unsupported fake E-Plus SQL: %s") % sql)

    def _set_rows(self, rows):
        self._result = rows

    def _first_product_row(self, product_serial):
        rows = self.connection._product_rows.get(product_serial) or []
        if not rows:
            return {}
        return rows[0]

    def _inventory_rows_for_product(self, store_serial, product_serial):
        product_lines = self.connection._product_rows.get(product_serial) or []
        if not product_lines:
            return []
        idx = self.connection._inventory_select_count[product_serial]
        self.connection._inventory_select_count[product_serial] += 1
        line = product_lines[idx] if idx < len(product_lines) else product_lines[-1]
        line_source = line.get("source") or {}
        line_inputs = line.get("inputs") or {}
        item = {
            "source_id": int(line_source["c_id"]),
            "product_eplus_serial": product_serial,
            "store_eplus_serial": store_serial,
            "price": self._float(line_inputs["itm_sell"]),
            "qty_in_small_unit": self._float(line_inputs["qnty"]),
            "qty": self._float(line_inputs["qnty"]),
            "cost": self._float(line_inputs["itm_cost"]),
            "exp_date": "2099-12-31 00:00:00",
        }
        if self.as_dict:
            return [item]
        return [tuple(item.values())]

    @staticmethod
    def _float(value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def _header_from_params(params):
        keys = [
            "temp_col6", "sto_id", "cust_id", "bill_typ", "no_of_items",
            "no_of_items_exc", "total_bill", "temp_col8", "total_bill_exc",
            "total_dis_per", "total_des_mon", "emp_id", "sth_notice",
            "sth_cash", "sth_rest", "sec_insert_uid", "sth_flag",
            "sth_extra_expenses", "total_bill_after_disc", "total_bill_net",
            "fh_contract_id", "fh_company_part", "fh_medins_rec_name",
            "fh_medins_ticket_num", "fh_medins_ins_num", "fh_medins_doc_name",
            "fh_clinic_id", "fh_clinic_spec_id", "fh_doc_spec_id",
            "sth_delivery_rest", "sth_pc_name", "sth_pont", "sth_pnt_dis",
            "temp_col4", "sth_cost_profit_perc", "total_tax",
        ]
        return {key: params[idx] if idx < len(params) else None for idx, key in enumerate(keys)}

    @staticmethod
    def _line_from_params(params):
        keys = [
            "std_id", "sth_id", "itm_id", "c_id", "exp_date", "qnty",
            "itm_sell", "itm_cost", "itm_dis_mon", "itm_dis_per",
            "sec_insert_uid", "itm_unit", "itm_aver_cost", "itm_nexist",
            "std_itm_origin", "itm_tax",
        ]
        return {key: params[idx] if idx < len(params) else None for idx, key in enumerate(keys)}
