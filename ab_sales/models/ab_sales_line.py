import math
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape


class AbdinSalesLines(models.Model):
    _name = 'ab_sales_line'
    _inherit = ['ab_product_qty', 'abdin_et.extra_tools']
    _description = 'ab_sales_line'
    _rec_name = 'product_id'

    product_id = fields.Many2one('ab_product', required=True, index=True)
    product_code = fields.Char(related='product_id.code', string='Code')

    header_id = fields.Many2one(
        'ab_sales_header', required=True, ondelete='cascade'
    )

    # Json field نظيف – مفيش legacy strings
    inventory_json = fields.Json(
        string="Inventory JSON",
        store=True,
        default=lambda self: {},
        help="Structured inventory data: {'data': [...]}",
    )

    customer_id = fields.Many2one(related='header_id.customer_id')
    customer_phone = fields.Char(related='header_id.customer_phone')
    customer_address = fields.Char(related='header_id.bill_customer_address')
    customer_name = fields.Char(related='header_id.bill_customer_name')
    invoice_number = fields.Integer(related='header_id.eplus_serial')
    employee_id = fields.Many2one(related='header_id.employee_id')

    balance = fields.Float(
        compute='_compute_inventory_data',
        string='Total Balance',
        store=True,
        compute_sudo=True,
    )
    price = fields.Float(
        compute='_compute_inventory_data',
        store=True,
        compute_sudo=True,
    )
    available_prices = fields.Char(
        compute='_compute_inventory_data', store=True, compute_sudo=True
    )
    available_prices_html = fields.Html(
        compute='_compute_available_prices_html',
        string="Price:Balance",
    )
    sell_price = fields.Float(
        compute='_compute_sell_price',
        store=True,
        readonly=False,
        default=0,
    )
    target_sell_price = fields.Float()
    cost = fields.Float(
        compute='_compute_inventory_data',
        store=True,
        compute_sudo=True,
    )
    net_amount = fields.Float(compute='_compute_net_amount')
    products_not_exist = fields.Boolean()
    header_status = fields.Selection(related='header_id.status')

    inventory_table_html = fields.Html(
        string='Batches (Unique)',
        compute='_compute_inventory_table_html',
        sanitize=True,
        store=False,
        readonly=True,
    )

    uom_id = fields.Many2one(
        'ab_product_uom',
        string="UoM",
        domain="[('category_id', '=', product_uom_category_id)]",
    )
    product_uom_category_id = fields.Many2one(
        related='product_id.uom_category_id',
        readonly=True,
        store=False,
    )
    price_subtotal = fields.Float(compute='_compute_amount', store=True)
    price_tax = fields.Float(compute='_compute_amount', store=True)

    unavailable_reason = fields.Selection([
        ('not_transferred', 'Not transferred yet from main store'),
        ('wrong_price', 'Wrong price in system'),
        ('stocktaking_error', 'Stocktaking error'),
        ('not_entered', 'Not entered by data entry yet'),
        ('promised_customer', 'Already told customer we will deliver product'),
        ('other', 'Other (please explain)'),
    ], string="Reason for selling without stock")

    unavailable_reason_other = fields.Char(
        string="Other reason (details)",
        help="Explain in more detail if you chose 'Other'.",
    )

    active = fields.Boolean(default=True)

    def _price_badge_allowed_sell_prices(self):
        self.ensure_one()
        if not self.product_id:
            return []

        payload = self.inventory_json or {}
        if not isinstance(payload, dict):
            payload = {}
        rows = payload.get("data") or []

        prices = [float(self.product_id.default_price or 0.0)]
        for row in rows:
            if not isinstance(row, dict):
                continue
            price = row.get("price")
            qty = row.get("qty") or 0.0
            if price is None:
                continue
            try:
                qty = float(qty or 0.0)
                price = float(price or 0.0)
            except Exception:
                continue
            if qty < 0.01:
                continue
            prices.append(price)

        prices = sorted(set(prices))
        if not self.product_id.is_priced and prices:
            prices = [max(prices)]

        default_factor = self.product_id.uom_id.factor if self.product_id.uom_id else 1.0
        selected_factor = self.uom_id.factor if self.uom_id else default_factor
        try:
            default_factor = float(default_factor or 0.0)
            selected_factor = float(selected_factor or 0.0)
        except Exception:
            default_factor = 0.0
            selected_factor = 0.0
        ratio = selected_factor / default_factor if default_factor > 0 and selected_factor > 0 else 1.0
        return [price * ratio for price in prices]

    def _sell_price_matches_price_badges(self):
        self.ensure_one()
        allowed_prices = self._price_badge_allowed_sell_prices()
        sell_price = float(self.sell_price or 0.0)
        return any(math.isclose(sell_price, price, abs_tol=0.01) for price in allowed_prices)

    @api.constrains('sell_price', 'product_id', 'inventory_json', 'uom_id')
    def _check_sell_price_in_available_prices(self):
        for line in self:
            if not line.product_id:
                continue
            if line._sell_price_matches_price_badges():
                continue
            allowed_prices = ", ".join(
                f"{price:.2f}".rstrip("0").rstrip(".")
                for price in line._price_badge_allowed_sell_prices()
            )
            raise ValidationError(
                _("Sell price %(price).2f for product %(product)s must be one of the available prices: %(prices)s.")
                % {
                    "price": float(line.sell_price or 0.0),
                    "product": line.product_id.display_name,
                    "prices": allowed_prices or _("none"),
                }
            )

    # ------------------------------------------------------------------ #
    # HTML of available prices
    # ------------------------------------------------------------------ #
    @api.depends('inventory_json', 'product_id', 'product_id.default_price')
    def _compute_available_prices_html(self):
        for rec in self:
            if not rec.product_id:
                rec.available_prices_html = ""
                continue

            payload = rec.inventory_json or {}
            if not isinstance(payload, dict):
                payload = {}
            rows = payload.get("data") or []

            price_qty = defaultdict(float)
            for row in rows:
                price = row.get("price")
                qty = row.get("qty") or 0.0
                if price is None:
                    continue
                if float(qty) < 0.01:
                    continue
                price_qty[price] += float(qty)

            default_price = rec.product_id.default_price or 0.0
            if default_price in price_qty:
                default_qty = price_qty.pop(default_price)
            else:
                default_qty = 0.0

            badges = []

            default_qty_txt = f"{default_qty:.3f}".rstrip('0').rstrip('.')
            default_price_txt = f"{default_price:.2f}".rstrip('0').rstrip('.')
            default_price_badge = 'text-bg-info' if default_qty else 'text-bg-danger'
            badges.append(
                f"<span class='badge {default_price_badge} fw-semibold px-2 py-1'>"
                f"{html_escape(default_price_txt)} : {html_escape(default_qty_txt)}"
                "</span>"
            )

            color_classes = [
                'text-success border border-success',
                'text-info border border-info',
                'text-warning border border-warning',
                'text-danger border border-danger',
                'text-dark border border-dark',
            ]
            other_prices = sorted(price_qty.keys())
            for idx, price in enumerate(other_prices):
                qty = price_qty[price]
                if isinstance(qty, (int, float)) and float(qty).is_integer():
                    qty_txt = f"{int(qty)}"
                else:
                    qty_txt = f"{qty:.3f}".rstrip('0').rstrip('.')

                price_txt = f"{price:.2f}".rstrip('0').rstrip('.')
                color_class = color_classes[idx % len(color_classes)]
                badges.append(
                    f"<span class='badge bg-light {color_class} px-2 py-1'>"
                    f"{html_escape(price_txt)} : {html_escape(qty_txt)}"
                    "</span>"
                )

            rec.available_prices_html = (
                "<div class='d-flex flex-wrap gap-1'>"
                + "".join(badges)
                + "</div>"
                if badges
                else ""
            )

    # ---------------------------- Amounts ---------------------------- #
    @api.depends('sell_price', 'qty')
    def _compute_amount(self):
        for line in self:
            subtotal = (line.sell_price or 0.0) * (line.qty or 0.0)
            line.price_subtotal = subtotal
            taxes = {
                'total_included': subtotal,
                'total_excluded': subtotal,
                'total_tax': 0.0,
            }
            line.price_tax = taxes.get('total_tax', 0.0)

    @api.depends('product_id', 'product_id.default_price')
    def _compute_sell_price(self):
        for rec in self:
            if rec.header_id.status not in ('saved', 'pending'):
                rec.sell_price = rec.product_id.default_price

    # ------------------- Inventory table HTML ------------------------ #
    @api.depends('inventory_json')
    def _compute_inventory_table_html(self):
        for rec in self:
            payload = rec.inventory_json or {}
            if not isinstance(payload, dict):
                payload = {}
            items = payload.get('data') or []

            item_d = defaultdict(float)
            for it in items:
                qty = it.get('qty') or 0.0
                price = it.get('price')
                exp_date = it.get('exp_date')
                exp = exp_date and str(exp_date).split(' ')[0]
                item_d[(price, exp)] += qty

            unique_rows = [{
                'qty': qty,
                'price': price,
                'exp': exp,
            } for (price, exp), qty in item_d.items()]

            unique_rows.sort(
                key=lambda row: (row['exp'] or '', row['qty'] or 0),
                reverse=True,
            )

            if unique_rows:
                tr_html = []
                for r in unique_rows:
                    if isinstance(r['qty'], (int, float)) and float(r['qty']).is_integer():
                        qty_txt = f"{int(r['qty'])}"
                    else:
                        qty_txt = f"{r['qty']}"
                    price_txt = f"{r['price']}"
                    exp_txt = r['exp'] or ''
                    tr_html.append(
                        "<tr>"
                        f"<td>{html_escape(price_txt)}</td>"
                        f"<td>{html_escape(exp_txt)}</td>"
                        f"<td>{html_escape(qty_txt)}</td>"
                        "</tr>"
                    )
                body = "".join(tr_html)
            else:
                body = (
                    "<tr><td colspan='3' "
                    "style='text-align:center;color:#888'>No data</td></tr>"
                )

            rec.inventory_table_html = (
                "<table class='o_list_view table table-sm' style='width:100%;'>"
                "<thead><tr>"
                "<th>Price</th><th>Exp. Date</th><th>Qty</th>"
                "</tr></thead>"
                f"<tbody>{body}</tbody>"
                "</table>"
            )

    # ----------------------- E-Plus helpers -------------------------- #
    def get_store_id(self, eplus_serial):
        return self.env['ab_store'].search(
            [('eplus_serial', '=', eplus_serial)], limit=1
        ).id

    def get_product_id(self, eplus_serial):
        return self.env['ab_product'].search(
            [('eplus_serial', '=', eplus_serial)], limit=1
        ).id

    # @api.depends('product_id')
    # def _compute_uom_id_domain(self):
    #     for rec in self:
    #         domain = rec._get_uom_id_domain()
    #         rec.uom_id_domain = json.dumps(domain)
    #
    # def _get_uom_id_domain(self):
    #     uom_list = [self.product_id.unit_l_id.id]
    #     if self.product_id.unit_m_id.unit_no > 1:
    #         uom_list.append(self.product_id.unit_m_id.id)
    #     if self.product_id.unit_s_id.unit_no > 1:
    #         uom_list.append(self.product_id.unit_s_id.id)
    #     return [('id', 'in', uom_list)]

    # ---------------------- Inventory recompute ---------------------- #


    # ---------------------- Inventory data compute ------------------- #
    @api.depends('product_id', 'header_id.store_id', 'inventory_json')
    def _compute_inventory_data(self):
        for rec in self:
            balance = 0.0
            price = 0.0
            available_prices = ""
            cost = 0.0

            if rec.product_id:
                payload = rec.inventory_json or {}
                if not isinstance(payload, dict):
                    payload = {}
                rows = payload.get("data") or []

                json_prices = [str(row.get('price')) for row in rows if 'price' in row]
                json_prices.append(str(rec.product_id.default_price))
                available_prices = '  ,  '.join(sorted(set(json_prices)))

                if rows:
                    price = rows[0].get('price', 0.0)
                    cost = rows[0].get('cost', 0.0)

                for d in rows:
                    balance += d.get('qty', 0.0)

            rec.balance = round(balance, 3)
            rec.price = price
            rec.available_prices = available_prices
            rec.cost = cost

    # ---------------------- Net & discount --------------------------- #
    @api.depends('sell_price', 'qty')
    def _compute_net_amount(self):
        for rec in self:
            rec.net_amount = rec.qty * rec.sell_price

    # ---------------------- Button helpers --------------------------- #
    def btn_get_product_balance(self):
        html = self.product_id._get_all_stores_balance_html([self.product_id.eplus_serial])
        return self.ab_msg(title="Store Balances", message=html)

    @api.onchange('product_id')
    def _fetch_branch_inventory_data(self):
        if not self.header_id.store_id:
            return
        if self.product_id and self.product_id.uom_id:
            self.uom_id = self.product_id.uom_id
        else:
            self.uom_id = False
        self._recompute_inventory_json()
