from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools.translate import _



class ProductPriced(models.Model):
    _name = 'ab_product_priced'
    _description = 'ab_product_priced'

    product_id = fields.Many2one('ab_product', index=True)
    product_code = fields.Char(index=True)
    is_priced = fields.Boolean(default=False, index=True)
    notes = fields.Char()
    active = fields.Boolean(default=True)


class ProductMetaData(models.Model):
    _name = 'ab_product_metadata'
    _description = 'ab_product_metadata'

    product_id = fields.Many2one('ab_product', required=True, index=True)
    product_code = fields.Char(index=True)
    is_priced = fields.Boolean(default=False, index=True)
    notes = fields.Char()
    active = fields.Boolean(default=True)

    _uniq_product_id = models.Constraint(
        "UNIQUE(product_id)",
        "Product metadata already exists for this product.",
    )

    @api.model
    def _normalize_product_code(self, code):
        return " ".join(str(code or "").strip().split())

    @api.model
    def _products_by_code(self, codes):
        normalized_codes = [self._normalize_product_code(code) for code in codes]
        normalized_codes = [code for code in normalized_codes if code]
        if not normalized_codes:
            return {}

        Product = self.env['ab_product'].sudo().with_context(active_test=False)
        products = Product.search([('code', 'in', list(set(normalized_codes)))])
        products_by_code = {}
        duplicate_codes = set()
        for product in products:
            code = self._normalize_product_code(product.code)
            if not code:
                continue
            if code in products_by_code:
                duplicate_codes.add(code)
            products_by_code[code] = product
        if duplicate_codes:
            raise UserError(
                _("Product code must be unique to import pricing flags. Duplicate code(s): %s")
                % ", ".join(sorted(duplicate_codes))
            )
        return products_by_code

    @api.model
    def _prepare_product_code_vals(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        products_by_code = self._products_by_code(
            vals.get('product_code')
            for vals in vals_list
            if 'product_code' in vals and vals.get('product_code')
        )

        product_ids = []
        for vals in vals_list:
            product_id = vals.get('product_id')
            if isinstance(product_id, (list, tuple)):
                product_id = product_id[0] if product_id else False
            try:
                product_id = int(product_id or 0)
            except Exception:
                product_id = 0
            if product_id:
                vals['product_id'] = product_id
                product_ids.append(product_id)
        products_by_id = {
            product.id: product
            for product in self.env['ab_product'].sudo().with_context(active_test=False).browse(product_ids).exists()
        } if product_ids else {}

        for vals in vals_list:
            has_code = 'product_code' in vals
            code = self._normalize_product_code(vals.get('product_code')) if has_code else ""
            if has_code:
                vals['product_code'] = code
                if code:
                    product = products_by_code.get(code)
                    if not product:
                        raise UserError(_("Product code '%s' was not found.") % code)
                    if vals.get('product_id') and vals['product_id'] != product.id:
                        raise UserError(_("Product code '%s' does not match the selected product.") % code)
                    vals['product_id'] = product.id
                elif not vals.get('product_id'):
                    vals['product_id'] = False

            if vals.get('product_id') and not vals.get('product_code'):
                product = products_by_id.get(vals['product_id'])
                if not product:
                    product = self.env['ab_product'].sudo().with_context(active_test=False).browse(
                        vals['product_id']).exists()
                vals['product_code'] = product.code if product else ""
            elif vals.get('product_id') is False:
                vals['product_code'] = ""
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(self._prepare_product_code_vals(vals_list))

    def write(self, vals):
        vals_list = [dict(vals) for _record in self]
        prepared_vals = self._prepare_product_code_vals(vals_list)
        first_vals = prepared_vals[0] if prepared_vals else {}
        if all(record_vals == first_vals for record_vals in prepared_vals):
            return super().write(first_vals)

        result = True
        for record, record_vals in zip(self, prepared_vals):
            result = super(ProductMetaData, record).write(record_vals) and result
        return result

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            rec.product_code = rec.product_id.code or ""


class Product(models.Model):
    _name = 'ab_product'
    _inherit = ['abdin_et.extra_tools', 'ab_product']

    balance = fields.Float(compute='_compute_balance')
    has_balance = fields.Boolean(compute='_compute_has_balance', search='_search_has_balance')
    has_pos_balance = fields.Boolean(compute='_compute_has_pos_balance', search='_search_has_pos_balance')
    only_default_sales_uom = fields.Boolean(default=False)

    @api.model
    def _search_display_name(self, operator, value):
        if not self.env.context.get("ab_bill_wizard_product_search"):
            return super()._search_display_name(operator, value)

        product_query = " ".join(str(value or "").strip().split())
        if not product_query:
            return super()._search_display_name(operator, value)

        exact_code_products = self.search([("code", "=ilike", product_query)], limit=400)
        if exact_code_products:
            return [("id", "in", exact_code_products.ids)]

        query_like = "%" + product_query.replace("*", "%").replace(" ", "%") + "%"
        domain = fields.Domain("name", "=ilike", query_like)
        if "product_card_name" in self._fields:
            domain |= fields.Domain("product_card_name", "=ilike", query_like)
        return list(domain)

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
        product_serials = []
        for serial in self.mapped('eplus_serial'):
            try:
                serial_int = int(serial or 0)
            except Exception:
                serial_int = 0
            if serial_int:
                product_serials.append(serial_int)

        balance_by_serial = {}
        if product_serials:
            self.env.cr.execute("""
                                select product_eplus_serial, sum(balance) as balance
                                from ab_sales_inventory
                                where product_eplus_serial = any (%s)
                                  and store_id is not null
                                  and balance != 0
                                group by product_eplus_serial
                                having sum(balance) > 0
                                """, (product_serials,))
            balance_by_serial = {
                int(serial): float(balance or 0.0)
                for serial, balance in self.env.cr.fetchall()
                if serial
            }

        for rec in self:
            try:
                rec_serial = int(rec.eplus_serial or 0)
            except Exception:
                rec_serial = 0
            rec.balance = balance_by_serial.get(rec_serial, 0.0)

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
                            where store_id is not null
                              and balance != 0
                            group by product_eplus_serial
                            having sum(balance) > 0
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
