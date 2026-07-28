from collections import defaultdict
from datetime import datetime
import logging
from math import floor

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _

PARAM_STR = "?"
_logger = logging.getLogger(__name__)


class AbSalesPromoReportLine(models.Model):
    _name = "ab_sales_promo_report_line"
    _description = "Sales Promo Report Line"
    _order = "invoice_date desc, invoice_eplus_serial desc, product_code"
    _rec_name = "invoice_eplus_serial"

    store_id = fields.Many2one("ab_store", string="Store", index=True, readonly=True)
    store_name = fields.Char(related="store_id.name", string="Store Name", store=True, readonly=True)
    store_eplus_serial = fields.Integer(string="Store EPlus Serial", index=True, readonly=True)
    invoice_eplus_serial = fields.Integer(string="Invoice EPlus Serial", index=True, readonly=True)
    product_id = fields.Many2one("ab_product", string="Product", index=True, readonly=True)
    product_code = fields.Char(related="product_id.code", string="Product Code", store=True, readonly=True)
    product_name = fields.Char(related="product_id.name", string="Product Name", store=True, readonly=True)
    product_eplus_serial = fields.Integer(string="Product EPlus Serial", index=True, readonly=True)
    qty = fields.Float(string="Qty", readonly=True, aggregator="sum")
    price = fields.Float(string="Price", readonly=True)
    total_price = fields.Float(string="Total Price", readonly=True, aggregator="sum")
    total_invoice = fields.Float(string="Total Invoice", readonly=True, aggregator=False)
    total_invoice_after_discount = fields.Float(
        string="Total Invoice After Discount",
        readonly=True,
        aggregator=False,
    )
    total_invoice_after_promo = fields.Float(
        string="Total Invoice After Promo",
        readonly=True,
        aggregator=False,
    )
    total_compensation = fields.Float(
        string="Total Compensation",
        readonly=True,
        aggregator=False,
        help="Difference between total_bill and total_bill_net from BConnect.",
    )
    promo_discount = fields.Float(
        string="Promo Discount",
        readonly=True,
        aggregator=False,
        help="Expected invoice-level discount from the matched local promotion rule.",
    )
    is_odoo = fields.Boolean(string="Odoo Invoice", index=True, readonly=True)
    invoice_date = fields.Date(string="Invoice Date", index=True, readonly=True)
    promo_id = fields.Many2one("ab_promo_program", string="Promo", index=True, readonly=True)
    promo_start = fields.Datetime(related="promo_id.rule_date_from", string="Promo Start", store=True, readonly=True)
    promo_end = fields.Datetime(related="promo_id.rule_date_to", string="Promo End", store=True, readonly=True)
    promo_date_status = fields.Selection(
        [
            ("in_date", "In Promo Date"),
            ("out_of_date", "Out of Promo Date"),
            ("no_promo_found", "No Promo Found"),
            ("no_promo_applied", "No Promo Applied"),
        ],
        string="Promo Date Status",
        default="in_date",
        index=True,
        readonly=True,
    )


class AbSalesPromoReportWizard(models.TransientModel):
    _name = "ab_sales_promo_report_wizard"
    _description = "Load Sales Promo Report"
    _inherit = "ab_eplus_connect"

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self))
    date_to = fields.Date(required=True, default=lambda self: fields.Date.context_today(self))
    store_ids = fields.Many2many("ab_store", string="Stores")
    product_ids = fields.Many2many("ab_product", string="Products")
    promo_ids = fields.Many2many("ab_promo_program", string="Promos")
    exclude_store_eplus_serial = fields.Integer(string="Exclude Store EPlus Serial", default=140)
    include_promo_notice = fields.Boolean(string="Invoices Marked With Promo Notice", default=True)
    include_off_customer = fields.Boolean(string="Invoices For Off Customers", default=True)
    include_no_promo_found = fields.Boolean(
        string="Include Lines With No Promo Found",
        help="If enabled, BConnect rows with no matching local promo are included and marked as No Promo Found.",
    )
    show_all_matching_promos = fields.Boolean(
        string="Show All Matching Promos",
        help="If enabled, an invoice line can appear once for each matching promo.",
    )
    replace_existing = fields.Boolean(
        string="Replace Existing Report Lines",
        default=True,
        help="Delete your previously loaded report lines in the selected date range before loading again.",
    )

    def action_load_report(self):
        self.ensure_one()
        date_from = fields.Date.to_date(self.date_from)
        date_to = fields.Date.to_date(self.date_to)
        if date_from > date_to:
            raise UserError(_("Date From must be before Date To."))
        if not self.include_promo_notice and not self.include_off_customer:
            raise UserError(_("Select at least one invoice filter."))

        rows = self._fetch_bconnect_rows()
        vals_list = self._build_report_vals(rows)

        ReportLine = self.env["ab_sales_promo_report_line"]
        if self.replace_existing:
            ReportLine.search([
                ("create_uid", "=", self.env.uid),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ]).unlink()

        lines = ReportLine.create(vals_list) if vals_list else ReportLine.browse()
        if not lines:
            if rows:
                raise UserError(_(
                    "BConnect returned %s line(s), but no lines matched local stores/products/promotions. "
                    "Use 'Show BConnect Query' to verify the SQL, then check eplus_serial mappings and promo dates/products. "
                    "Enable 'Include Lines With No Promo Found' to include unmatched rows."
                ) % len(rows))
            raise UserError(_("No matching sales promo lines were found. BConnect returned no rows."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Promo Report"),
            "res_model": "ab_sales_promo_report_line",
            "view_mode": "list,pivot,graph",
            "domain": [("id", "in", lines.ids)],
            "context": {"create": False, "edit": False, "delete": True},
        }

    def action_show_query(self):
        self.ensure_one()
        query, params = self._prepare_bconnect_query()
        raise UserError("%s\n\n%s" % (
            _("BConnect SQL Query"),
            self._format_debug_sql(query, params),
        ))

    def _fetch_bconnect_rows(self):
        query, params = self._prepare_bconnect_query()
        _logger.info(
            "Sales Promo Report BConnect SQL:\n%s",
            self._format_debug_sql(query, params),
        )
        with self.connect_eplus(param_str=PARAM_STR, charset="CP1256") as conn:
            with conn.cursor(as_dict=True) as cur:
                cur.execute(query, tuple(params))
                return cur.fetchall()

    def _prepare_bconnect_query(self):
        store_serials = self.store_ids.mapped("eplus_serial")
        product_serials = self.product_ids.mapped("eplus_serial")

        where = [
            f"h.sec_insert_date >= {PARAM_STR}",
            f"h.sec_insert_date < DATEADD(day, 1, {PARAM_STR})",
        ]
        params = [
            fields.Date.to_string(fields.Date.to_date(self.date_from)),
            fields.Date.to_string(fields.Date.to_date(self.date_to)),
        ]

        if self.exclude_store_eplus_serial:
            where.append(f"h.sto_id != {PARAM_STR}")
            params.append(int(self.exclude_store_eplus_serial))

        if store_serials:
            where.append(self._sql_in_clause("h.sto_id", store_serials, params))

        if product_serials:
            where.append(self._sql_in_clause("d.itm_id", product_serials, params))

        odoo_marker = "ISNULL(h.sth_notice, '') LIKE N'%§§§%'"
        off_customer_marker = "ISNULL(c.cust_code, '') LIKE '%off%'"
        marker_parts = []
        if self.include_promo_notice:
            marker_parts.append(odoo_marker)
        if self.include_off_customer:
            marker_parts.append(off_customer_marker)
        where.append("(" + " OR ".join(marker_parts) + ")")

        query = f"""
            SELECT
                h.sth_id AS invoice_eplus_serial,
                h.sto_id AS store_eplus_serial,
                CAST(ISNULL(h.total_bill, 0) AS DECIMAL(38, 6)) AS total_bill,
                CAST(ISNULL(h.total_bill_after_disc, 0) AS DECIMAL(38, 6)) AS total_bill_after_disc,
                CAST(ISNULL(h.total_bill_net, 0) AS DECIMAL(38, 6)) AS total_bill_net,
                d.itm_id AS product_eplus_serial,
                CAST(SUM(ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) AS DECIMAL(38, 6)) AS qty,
                CAST(ISNULL(d.itm_sell, 0) AS DECIMAL(38, 6)) AS price,
                CAST(SUM((ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) * ISNULL(d.itm_sell, 0)) AS DECIMAL(38, 6))
                    AS total_price,
                CAST(h.sec_insert_date AS DATE) AS invoice_date,
                CAST(MAX(CASE WHEN {odoo_marker} THEN 1 ELSE 0 END) AS BIT) AS is_odoo,
                MIN(h.sec_insert_date) AS invoice_datetime
            FROM r_sales_trans_h h WITH (NOLOCK)
            JOIN r_sales_trans_d d WITH (NOLOCK)
                ON h.sth_id = d.sth_id
                AND h.sto_id = d.std_stock_id
            LEFT JOIN Customer c WITH (NOLOCK)
                ON c.cust_id = h.cust_id
            WHERE {" AND ".join(where)}
            GROUP BY
                h.sth_id,
                h.sto_id,
                d.itm_id,
                d.itm_sell,
                h.total_bill,
                h.total_bill_after_disc,
                h.total_bill_net,
                h.sec_insert_date
        """

        return query, params

    @classmethod
    def _format_debug_sql(cls, query, params):
        parts = query.split(PARAM_STR)
        if len(parts) == 1:
            return query.strip()

        rendered = [parts[0]]
        for index, param in enumerate(params):
            rendered.append(cls._format_sql_value(param))
            rendered.append(parts[index + 1] if index + 1 < len(parts) else "")
        if len(parts) > len(params) + 1:
            rendered.extend(parts[len(params) + 1:])
        return "".join(rendered).strip()

    @staticmethod
    def _format_sql_value(value):
        if value is None:
            return "NULL"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, datetime):
            value = fields.Datetime.to_string(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    @staticmethod
    def _sql_in_clause(column, values, params):
        clean_values = [int(value) for value in values if value]
        placeholders = ", ".join([PARAM_STR] * len(clean_values))
        params.extend(clean_values)
        return f"{column} IN ({placeholders})"

    def _build_report_vals(self, rows):
        if not rows:
            return []

        stores_by_serial = self._records_by_eplus("ab_store", rows, "store_eplus_serial")
        products_by_serial = self._records_by_eplus("ab_product", rows, "product_eplus_serial")
        stores = self.env["ab_store"].sudo().browse([store.id for store in stores_by_serial.values()])
        promos = self._promo_candidates(stores) if stores else self.env["ab_promo_program"].browse()
        promo_scope_by_id = {
            promo.id: self._program_report_products(promo)
            for promo in promos
        }

        invoice_rows = defaultdict(list)
        for row in rows:
            invoice_key = (
                self._row_int(row, "invoice_eplus_serial"),
                self._row_int(row, "store_eplus_serial"),
                self._row_date(row, "invoice_date"),
            )
            invoice_rows[invoice_key].append(row)

        vals_list = []
        for invoice_key, grouped_rows in invoice_rows.items():
            store = stores_by_serial.get(invoice_key[1])
            invoice_products = self.env["ab_product"].sudo().browse([
                products_by_serial[product_serial].id
                for product_serial in {
                    self._row_int(row, "product_eplus_serial")
                    for row in grouped_rows
                }
                if product_serial in products_by_serial
            ])
            invoice_compensation = self._invoice_total_compensation(grouped_rows)
            is_odoo = any(self._row_bool(row, "is_odoo") for row in grouped_rows)
            candidate_promos = self._product_matching_promos(
                promos,
                promo_scope_by_id,
                store,
                invoice_products,
            )
            matched_promo, promo_discount = self._matched_promo_for_invoice(
                candidate_promos,
                promo_scope_by_id,
                grouped_rows,
                products_by_serial,
                store,
                invoice_compensation,
                is_odoo,
            )

            added_row_indexes = set()
            if matched_promo:
                promo_products = promo_scope_by_id.get(matched_promo.id, self.env["ab_product"])
                promo_date_status = self._promo_date_status(matched_promo, invoice_key[2])
                for row_index, row in enumerate(grouped_rows):
                    product = products_by_serial.get(self._row_int(row, "product_eplus_serial"))
                    if not product or product not in promo_products:
                        continue
                    vals_list.append(self._report_vals_from_row(
                        row,
                        store,
                        product,
                        matched_promo,
                        promo_discount,
                        promo_date_status,
                    ))
                    added_row_indexes.add(row_index)
            elif self._has_total_compensation(invoice_compensation) and candidate_promos:
                promo_products = self._promos_report_products(candidate_promos, promo_scope_by_id)
                for row_index, row in enumerate(grouped_rows):
                    product = products_by_serial.get(self._row_int(row, "product_eplus_serial"))
                    if not product or product not in promo_products:
                        continue
                    vals_list.append(self._report_vals_from_row(
                        row,
                        store,
                        product,
                        self.env["ab_promo_program"],
                        0.0,
                        "no_promo_applied",
                    ))
                    added_row_indexes.add(row_index)

            if self.include_no_promo_found:
                for row_index, row in enumerate(grouped_rows):
                    if row_index in added_row_indexes:
                        continue
                    product = products_by_serial.get(self._row_int(row, "product_eplus_serial"))
                    if not product:
                        continue
                    vals_list.append(self._report_vals_from_row(
                        row,
                        store,
                        product,
                        self.env["ab_promo_program"],
                        0.0,
                        "no_promo_found",
                    ))

        return vals_list

    def _records_by_eplus(self, model_name, rows, row_key):
        serials = {
            self._row_int(row, row_key)
            for row in rows
            if self._row_int(row, row_key)
        }
        if not serials:
            return {}
        records = self.env[model_name].sudo().search([("eplus_serial", "in", list(serials))])
        return {int(rec.eplus_serial): rec for rec in records if rec.eplus_serial}

    def _promo_candidates(self, stores=False):
        domain = [
            ("active", "=", True),
            "|", ("company_id", "=", self.env.company.id), ("company_id", "=", False),
        ]
        if stores:
            domain += ["|", ("store_ids", "=", False), ("store_ids", "in", stores.ids)]
        if self.promo_ids:
            domain.append(("id", "in", self.promo_ids.ids))
        return self.env["ab_promo_program"].sudo().search(domain, order="sequence,id")

    def _product_matching_promos(self, promos, promo_scope_by_id, store, invoice_products):
        if not store or not invoice_products:
            return promos.browse()

        matching = promos.browse()
        for promo in promos:
            if promo.store_ids and store not in promo.store_ids:
                continue
            scope = promo_scope_by_id.get(promo.id, self.env["ab_product"])
            if scope and (scope & invoice_products):
                matching |= promo
        return matching

    def _matched_promo_for_invoice(
        self,
        candidate_promos,
        promo_scope_by_id,
        rows,
        products_by_serial,
        store,
        invoice_compensation,
        is_odoo,
    ):
        if not self._has_total_compensation(invoice_compensation):
            return candidate_promos.browse(), 0.0

        tolerance = 1.0 if is_odoo else 5.0
        for promo in candidate_promos:
            promo_products = promo_scope_by_id.get(promo.id, self.env["ab_product"])
            promo_discount = self._promo_discount_for_invoice(
                rows,
                products_by_serial,
                store,
                promo,
                promo_products,
            )
            if abs(promo_discount - invoice_compensation) <= tolerance:
                return promo, promo_discount
        return candidate_promos.browse(), 0.0

    def _promos_report_products(self, promos, promo_scope_by_id):
        products = self.env["ab_product"].browse()
        for promo in promos:
            products |= promo_scope_by_id.get(promo.id, self.env["ab_product"])
        return products

    def _promo_date_status(self, promo, invoice_date):
        return "in_date" if self._promo_date_matches(promo, invoice_date) else "out_of_date"

    def _invoice_total_compensation(self, rows):
        if not rows:
            return 0.0
        row = rows[0]
        return self._row_float(row, "total_bill") - self._row_float(row, "total_bill_net")

    @staticmethod
    def _has_total_compensation(total_compensation):
        return abs(total_compensation) > 1e-8

    @api.model
    def _program_report_products(self, promo):
        Product = self.env["ab_product"].sudo()
        if promo.apply_disc_on == "specific_products" and promo.disc_specific_product_ids:
            return promo.disc_specific_product_ids
        if promo.product_ids:
            return promo.product_ids
        if promo.rule_products_domain:
            try:
                domain = safe_eval(promo.rule_products_domain, {})
                return Product.search(domain)
            except Exception:
                return Product.browse()
        return Product.browse()

    @staticmethod
    def _promo_date_matches(promo, invoice_date):
        if not invoice_date:
            return False
        date_from = fields.Date.to_date(promo.rule_date_from) if promo.rule_date_from else False
        date_to = fields.Date.to_date(promo.rule_date_to) if promo.rule_date_to else False
        if date_from and invoice_date < date_from:
            return False
        if date_to and invoice_date > date_to:
            return False
        return True

    def _promo_discount_for_invoice(self, rows, products_by_serial, store, promo, promo_products):
        sales_logic_discount = self._promo_discount_with_sales_logic(rows, products_by_serial, store, promo)
        if sales_logic_discount is not None:
            return sales_logic_discount

        promo_rows = [
            row for row in rows
            if self._row_product_in_products(row, products_by_serial, promo_products)
        ]
        if not promo_rows:
            return 0.0

        total_qty = sum(self._row_float(row, "qty") for row in promo_rows)
        need_qty = float(promo.rule_min_qty or 0.0)
        if need_qty > 0.0 and total_qty + 1e-8 < need_qty:
            return 0.0

        if promo.apply_disc_on in ("on_order", "specific_products"):
            pct = max(0.0, min(float(promo.disc_percent or 0.0), 100.0)) / 100.0
            return sum(self._row_float(row, "total_price") for row in promo_rows) * pct

        if promo.apply_disc_on == "fixed_price":
            fixed_price = float(promo.fixed_price or 0.0)
            if fixed_price <= 0.0:
                return 0.0
            return sum(
                max(self._row_float(row, "price") - fixed_price, 0.0) * self._row_float(row, "qty")
                for row in promo_rows
            )

        if promo.apply_disc_on == "cheapest_product":
            need = int(promo.rule_min_qty or 1)
            if need < 1:
                need = 1
            pct = max(0.0, min(float(promo.disc_percent or 0.0), 100000.0)) / 100.0
            if pct <= 0.0:
                return 0.0

            units = []
            for row in promo_rows:
                qty = int(floor(self._row_float(row, "qty") + 1e-8))
                if qty <= 0:
                    continue
                price = self._row_float(row, "price")
                if price < 0.0:
                    continue
                units.extend([price] * qty)
            units.sort(reverse=True)
            return sum(price * pct for index, price in enumerate(units) if (index + 1) % need == 0)

        return 0.0

    def _row_product_in_products(self, row, products_by_serial, products):
        product = products_by_serial.get(self._row_int(row, "product_eplus_serial"))
        return bool(product and product in products)

    def _promo_discount_with_sales_logic(self, rows, products_by_serial, store, promo):
        line_commands = []
        source_rows = []
        for row in rows:
            product = products_by_serial.get(self._row_int(row, "product_eplus_serial"))
            qty = self._row_float(row, "qty")
            if not product or qty <= 0.0:
                continue
            line_commands.append((0, 0, {
                "product_id": product.id,
                "qty_str": str(qty),
                "sell_price": self._row_float(row, "price"),
                "uom_id": product.uom_id.id if product.uom_id else False,
            }))
            source_rows.append(row)

        if not line_commands:
            return 0.0

        try:
            header = self.env["ab_sales_header"].with_context(force_program_effective=True).new({
                "store_id": store.id,
                "applied_program_ids": [(6, 0, [promo.id])],
                "line_ids": line_commands,
            })
            for line, row in zip(header.line_ids, source_rows):
                line.qty_str = str(self._row_float(row, "qty"))
                line._compute_qty()
                line.sell_price = self._row_float(row, "price")
            products = header.line_ids.mapped("product_id")
            amount_total = sum(
                float(line.qty or 0.0) * float(line.sell_price or 0.0)
                for line in header.line_ids
            )
            discount = sum(
                float(header._discount_for_program_on_product(promo, product) or 0.0)
                for product in products
            )
            return min(discount, amount_total)
        except Exception as ex:
            _logger.warning(
                "Falling back to report promo discount calculation for promo %s: %r",
                promo.id,
                ex,
            )
            return None

    def _report_vals_from_row(self, row, store, product, promo, promo_discount, promo_date_status):
        total_bill = self._row_float(row, "total_bill")
        total_bill_net = self._row_float(row, "total_bill_net")
        return {
            "store_id": store.id if store else False,
            "store_eplus_serial": self._row_int(row, "store_eplus_serial"),
            "invoice_eplus_serial": self._row_int(row, "invoice_eplus_serial"),
            "product_id": product.id if product else False,
            "product_eplus_serial": self._row_int(row, "product_eplus_serial"),
            "qty": self._row_float(row, "qty"),
            "price": self._row_float(row, "price"),
            "total_price": self._row_float(row, "total_price"),
            "total_invoice": total_bill,
            "total_invoice_after_discount": self._row_float(row, "total_bill_after_disc"),
            "total_invoice_after_promo": total_bill_net,
            "total_compensation": total_bill - total_bill_net,
            "promo_discount": promo_discount,
            "is_odoo": self._row_bool(row, "is_odoo"),
            "invoice_date": self._row_date(row, "invoice_date"),
            "promo_id": promo.id if promo else False,
            "promo_date_status": promo_date_status,
        }

    @staticmethod
    def _row_float(row, key):
        try:
            return float(row.get(key) or 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def _row_int(row, key):
        try:
            return int(row.get(key) or 0)
        except Exception:
            return 0

    @staticmethod
    def _row_bool(row, key):
        try:
            return bool(row.get(key))
        except Exception:
            return False

    @staticmethod
    def _row_date(row, key):
        value = row.get(key)
        if isinstance(value, datetime):
            return value.date()
        return fields.Date.to_date(value) if value else False
