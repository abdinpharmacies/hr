from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from .ab_sales_header import PARAM_STR
import logging

_logger = logging.getLogger(__name__)


class AbProduct(models.Model):
    _name = 'ab_product'
    _inherit = ['abdin_et.extra_tools', 'ab_eplus_connect', 'ab_product']

    balance = fields.Float(compute='_compute_balance')
    has_balance = fields.Boolean(compute='_compute_has_balance', search='_search_has_balance')
    has_pos_balance = fields.Boolean(compute='_compute_has_pos_balance', search='_search_has_pos_balance')

    def _context_pos_store_id(self):
        store_id = (
                self.env.context.get('pos_store_id')
                or self.env.context.get('store_id')
                or self.env.context.get('pos_id')
        )
        if isinstance(store_id, (list, tuple)):
            store_id = store_id and store_id[0]
        try:
            return int(store_id) if store_id else False
        except Exception:
            return False

    def action_get_pos_products_exist(self, pos_id):
        self.env.cr.execute("""
                            select product_eplus_serial
                            from ab_sales_inventory
                            where balance > 0
                              and store_id = %s
                            """, (pos_id,))
        eplus_serials = [row[0] for row in self.env.cr.fetchall()]

        return [('eplus_serial', 'in', eplus_serials)]

    def _compute_balance(self):
        eInv = self.env['ab_sales_inventory'].sudo()
        for rec in self:
            rec.balance = eInv.search([
                ('product_eplus_serial', '=', rec.eplus_serial),
                ('store_id', '=', False),
            ], limit=1).balance or 0

    def _compute_has_balance(self):
        for rec in self:
            rec.has_balance = bool(rec.balance)

    def _compute_has_pos_balance(self):
        store_id = self._context_pos_store_id()
        if not store_id:
            for rec in self:
                rec.has_pos_balance = False
            return

        product_serials = []
        for serial in self.mapped('eplus_serial'):
            try:
                serial_int = int(serial or 0)
            except Exception:
                serial_int = 0
            if serial_int:
                product_serials.append(serial_int)

        if not product_serials:
            for rec in self:
                rec.has_pos_balance = False
            return

        inv_rows = self.env['ab_sales_inventory'].sudo().search_read(
            [
                ('store_id', '=', store_id),
                ('product_eplus_serial', 'in', product_serials),
                ('balance', '>', 0),
            ],
            ['product_eplus_serial']
        )
        serials_with_balance = {int(r['product_eplus_serial']) for r in inv_rows if r.get('product_eplus_serial')}

        for rec in self:
            try:
                rec_serial = int(rec.eplus_serial or 0)
            except Exception:
                rec_serial = 0
            rec.has_pos_balance = bool(rec_serial and rec_serial in serials_with_balance)

    def _search_has_balance(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        self.env.cr.execute("""
                            select product_eplus_serial
                            from ab_sales_inventory
                            where balance > 0
                              and store_id is null
                            """)
        eplus_serials = [row[0] for row in self.env.cr.fetchall()]

        if operator != '=':  # that means it is '!='
            val = not val
        if val:
            return ['|', ('is_service', '=', True), ('eplus_serial', 'in', eplus_serials)]
        return [('eplus_serial', 'not in', eplus_serials)]

    def _search_has_pos_balance(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        store_id = self._context_pos_store_id()
        if not store_id:
            # No POS/store in context: do not unexpectedly hide products.
            return self._search_has_balance(operator, val)

        self.env.cr.execute("""
                            select product_eplus_serial
                            from ab_sales_inventory
                            where balance > 0
                              and store_id = %s
                            """, (store_id,))
        eplus_serials = [row[0] for row in self.env.cr.fetchall()]

        if operator != '=':  # that means it is '!='
            val = not val
        if val:
            return ['|', ('is_service', '=', True), ('eplus_serial', 'in', eplus_serials)]
        return [('eplus_serial', 'not in', eplus_serials)]

    def btn_get_stores_balance(self):
        html = self._get_all_stores_balance_html([self.eplus_serial])
        return self.ab_msg(title="Store Balances", message=html)

    @api.model
    def _get_all_stores_balance_html(self, product_serials=None):
        if not product_serials:
            return ""

        stores = self.env['ab_store'].sudo().search([('allow_sale', '=', True)])
        store_eplus_serials = ','.join(map(str, stores.mapped('eplus_serial')))

        prod_placeholders = ','.join(len(product_serials) * [PARAM_STR])

        rows = []
        offline_mode = False
        try:
            with self.connect_eplus(param_str=PARAM_STR, charset='CP1256') as conn:
                if not self.is_connection_valid(conn):
                    raise UserError(_("EPlus connection is not valid."))
                with conn.cursor() as crx:
                    sql = f"""
                        SELECT
                            main.itm_id AS product_eplus_serial,
                            main.sto_id AS store_eplus_serial,
                            s.sto_tel AS store_area,
                            SUM(CAST(main.itm_qty/ic.itm_unit1_unit3 AS decimal(18,2))) AS qty
                        FROM Item_Class_Store main WITH (NOLOCK)
                        JOIN item_catalog ic WITH (NOLOCK) ON main.itm_id = ic.itm_id
                        JOIN store s on main.sto_id = s.sto_id
                        WHERE main.itm_id IN ({prod_placeholders}) and main.sto_id in ({store_eplus_serials})
                        GROUP BY main.itm_id, main.sto_id, s.sto_tel
                        HAVING SUM(CAST(main.itm_qty/ic.itm_unit1_unit3 AS decimal(18,2))) > 0
                        ORDER BY main.itm_id, s.sto_tel, qty desc                    
                    """
                    crx.execute(sql, tuple(product_serials))
                    rows = crx.fetchall()  # [(prod_serial, store_serial, store_area, qty)]
        except Exception as ex:
            _logger.warning(
                "EPlus connection unavailable for store balances; falling back to ab_sales_inventory: %s",
                ex,
            )
            rows = self._get_stores_balance_rows_from_inventory(product_serials, stores)
            offline_mode = True

        # ---- Build lookup maps from Odoo for names by eplus_serial ----
        # product map: eplus_serial -> name
        prod_serial_set = {int(p[0]) for p in rows}
        store_serial_set = {int(p[1]) for p in rows}

        prod_records = self.env['ab_product'].sudo().search_read(
            [('eplus_serial', 'in', list(prod_serial_set))],
            ['eplus_serial', 'code', 'name']
        )
        store_records = self.env['ab_store'].sudo().search_read(
            [('eplus_serial', 'in', list(store_serial_set))],
            ['eplus_serial', 'code', 'name']
        )

        prod_map = {int(prod['eplus_serial']): (prod['code'], prod['name']) for prod in prod_records}
        store_map = {
            int(store['eplus_serial']): (store.get('code') or '', store.get('name') or '')
            for store in store_records
        }

        def _fmt_qty(q):
            try:
                q = float(q or 0.0)
            except Exception:
                q = 0.0
            s = f"{q:.2f}"
            return s.rstrip("0").rstrip(".")

        # Group by product serial
        rows_by_product = {}
        for prod_serial, store_serial, store_area, qty in rows:
            rows_by_product.setdefault(int(prod_serial or 0), []).append(
                (int(store_serial or 0), store_area or "", float(qty or 0.0))
            )

        products = []
        for prod_serial in sorted(rows_by_product.keys()):
            prod_code, prod_name = prod_map.get(prod_serial, ("—", "—"))
            prod_code = prod_code or "—"
            prod_name = prod_name or "—"
            prod_serial_str = str(prod_serial or "—")

            prod_rows = rows_by_product[prod_serial]
            total_qty = sum(q for __, ___, q in prod_rows)
            max_qty = max([q for __, ___, q in prod_rows] or [0.0]) or 0.0

            raw_rows = []
            for store_serial, store_area, qty in prod_rows:
                store_code, store_name = store_map.get(store_serial, ("", "—"))  # store_code unused (intentionally)
                store_name = store_name or "—"
                area_key = (store_area or "—")
                store_area = area_key

                pct = 0
                if max_qty > 0:
                    pct = max(2, int(round((qty / max_qty) * 100)))
                    pct = min(100, pct)

                raw_rows.append(
                    {
                        "store_name": store_name,
                        "store_area": store_area,
                        "qty": _fmt_qty(qty),
                        "pct": int(pct),
                    }
                )

            # Build 2-column rows, inserting <hr/> between areas (and never pairing across areas).
            table_rows_2col = []
            last_area = None
            pending_left = None
            row_index = 0
            for r in raw_rows:
                area = r["store_area"]
                if last_area is not None and area != last_area:
                    if pending_left:
                        table_rows_2col.append(
                            {
                                "key": f"{prod_serial}-pair-{row_index}",
                                "type": "pair",
                                "left": pending_left,
                                "right": None,
                            }
                        )
                        row_index += 1
                        pending_left = None
                    table_rows_2col.append(
                        {
                            "key": f"{prod_serial}-hr-{row_index}",
                            "type": "hr",
                        }
                    )
                    row_index += 1

                last_area = area
                if pending_left is None:
                    pending_left = r
                else:
                    table_rows_2col.append(
                        {
                            "key": f"{prod_serial}-pair-{row_index}",
                            "type": "pair",
                            "left": pending_left,
                            "right": r,
                        }
                    )
                    row_index += 1
                    pending_left = None

            if pending_left:
                table_rows_2col.append(
                    {
                        "key": f"{prod_serial}-pair-{row_index}",
                        "type": "pair",
                        "left": pending_left,
                        "right": None,
                    }
                )

            products.append(
                {
                    "serial": prod_serial_str,
                    "code": prod_code,
                    "name": prod_name,
                    "total_qty": _fmt_qty(total_qty),
                    "rows": table_rows_2col,
                }
            )

        single_product = len(products) == 1
        if single_product:
            products[0]["open"] = True

        return self.env["ir.qweb"]._render(
            "ab_sales.product_store_balance_html",
            {"products": products, "single_product": single_product, "offline_mode": offline_mode},
        )

    def _get_stores_balance_rows_from_inventory(self, product_serials, stores):
        serials = []
        for serial in product_serials or []:
            try:
                serial_int = int(serial or 0)
            except Exception:
                serial_int = 0
            if serial_int:
                serials.append(serial_int)

        if not serials or not stores:
            return []

        store_map = {store.id: store for store in stores}
        inv_lines = self.env['ab_sales_inventory'].sudo().search_read(
            [
                ('store_id', 'in', stores.ids),
                ('product_eplus_serial', 'in', serials),
                ('balance', '>', 0),
            ],
            ['product_eplus_serial', 'store_id', 'balance'],
        )

        rows = []
        for line in inv_lines:
            store_ref = line.get('store_id') or []
            store_id = store_ref[0] if store_ref else 0
            store = store_map.get(store_id)
            if not store:
                continue

            try:
                store_serial = int(store.eplus_serial or 0)
            except Exception:
                store_serial = 0
            if not store_serial:
                continue

            try:
                prod_serial = int(line.get('product_eplus_serial') or 0)
            except Exception:
                prod_serial = 0
            if not prod_serial:
                continue

            try:
                qty = float(line.get('balance') or 0.0)
            except Exception:
                qty = 0.0
            if qty <= 0.0:
                continue

            store_area = store.telephone or store.location or ""
            rows.append((prod_serial, store_serial, store_area, qty))

        rows.sort(key=lambda r: (r[0], r[2], -r[3]))
        return rows
