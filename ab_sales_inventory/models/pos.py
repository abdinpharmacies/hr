import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeSalesPOS(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        payload = payload if payload is not None else kwargs
        if isinstance(payload, dict) and self.env['ab_sales_backend']._is_native((payload.get('header') or {}).get('store_id')):
            self = self.with_context(native_pos_hr_token=payload.get('pos_hr_session_token'))
        return super().pos_submit(payload=payload)

    @api.model
    def pos_barcode_products(self, barcode=None, store_id=None):
        result = super().pos_barcode_products(barcode=barcode, store_id=store_id)
        if self.env['ab_sales_backend']._is_native(store_id):
            balances = self.pos_refresh_pos_balances(store_id, [row['id'] for row in result])
            for row in result:
                row.update(balance=balances.get(row['id'], 0), pos_balance=balances.get(row['id'], 0))
        return result

    @api.model
    def _native_inventory_rows(self, store_id, product):
        store = self.env['ab_sales_backend']._check_store(store_id)
        product.check_access('read')
        if not product or product.is_service:
            return []
        factor = product._to_stock_quantity(1, product.uom_id)
        stock = self.env['ab_inventory_process'].source_stock(store.id, product.ids)
        return [{
            'source_id': row['source_id'], 'source_identity': row['source_identity'],
            'store_id': store.id, 'store_eplus_serial': store.eplus_serial,
            'product_id': product.id, 'product_eplus_serial': product.eplus_serial,
            'qty': row['qty'] / factor, 'qty_in_small_unit': row['qty'],
            'price': row['price'] * factor, 'cost': row['cost'] * factor,
            'exp_date': row['expiry'] or False,
        } for row in stock.get(product.id, [])]

    @api.model
    def _pos_submit_response(self, header, apply_submit=True):
        if not header.native_backend:
            return super()._pos_submit_response(header, apply_submit=apply_submit)
        if apply_submit:
            header.action_submit()
        return {'id': header.id, 'status': header.status, 'eplus_serial': False, 'native_backend': True}

    @api.model
    def _fill_lines_balance_from_offline(self, header):
        if header.native_backend:
            header.line_ids._recompute_inventory_json()
            return
        return super()._fill_lines_balance_from_offline(header)

    @api.model
    def _store_default_price(self, store_id, product):
        if self.env['ab_sales_backend']._is_native(store_id):
            self.env['ab_sales_backend']._check_store(store_id)
            product.check_access('read')
            return product.default_price
        return super()._store_default_price(store_id, product)

    @api.model
    def pos_product_details(self, store_id, product_id):
        if not self.env['ab_sales_backend']._is_native(store_id):
            return super().pos_product_details(store_id, product_id)
        self.env['ab_sales_backend']._check_store(store_id)
        product = self.env['ab_product'].browse(int(product_id)).exists()
        product.check_access('read')
        if not product:
            raise ValidationError(_('Select an existing product.'))
        header = self.env['ab_sales_header'].new({'store_id': int(store_id), 'native_backend': True})
        line = self.env['ab_sales_line'].new({'header_id': header, 'product_id': product.id,
                                             'uom_id': product.uom_id.id, 'qty_str': '1'})
        line._recompute_inventory_json()
        line._compute_inventory_data()
        available = self.pos_refresh_pos_balances(store_id, [product.id])[product.id]
        return {
            'balance': available, 'total_balance': available, 'pos_balance': available,
            'cost': line.cost, 'sell_price': product.default_price,
            'available_prices': self._available_prices_list(line), 'is_priced': bool(product.is_priced),
            'inventory_table_html': line.inventory_table_html,
            'uom_id': product.uom_id.id, 'uom_name': product.uom_id.name,
            'uom_category_id': product.uom_category_id.id, 'uom_factor': product.uom_id.factor,
            'default_uom_id': product.uom_id.id, 'default_uom_factor': product.uom_id.factor,
            'only_default_sales_uom': product.only_default_sales_uom, 'default_price': product.default_price,
        }

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None):
        if not self.env['ab_sales_backend']._is_native(store_id):
            return super().pos_refresh_pos_balances(store_id=store_id, product_ids=product_ids)
        self.env['ab_sales_backend']._check_store(store_id)
        products = self.env['ab_product'].browse([int(pid) for pid in (product_ids or [])]).exists()
        products.check_access('read')
        balances = self.env['ab_inventory_process'].available_stock(int(store_id), products.ids)
        return {product.id: balances.get(product.id, 0) / (1.0 if product.is_service else product._to_stock_quantity(1, product.uom_id))
                for product in products}

    @api.model
    def pos_customer_lookup(self, phone=None, store_id=None):
        if not self.env['ab_sales_backend']._is_native(store_id):
            return super().pos_customer_lookup(phone=phone, store_id=store_id)
        store = self.env['ab_sales_backend']._check_store(store_id)
        phone = self._normalize_phone(phone)
        customer = self.env['ab_customer'].search([('mobile_phone', '=', phone),
                                                  ('default_store_id', '=', store.id)], limit=1)
        return {'status': 'found', 'customer': self._customer_payload(customer)} if customer else {'status': 'not_found'}

    @api.model
    def pos_customer_create(self, phone=None, name=None, address=None, store_id=None):
        if not self.env['ab_sales_backend']._is_native(store_id):
            return super().pos_customer_create(phone=phone, name=name, address=address, store_id=store_id)
        store = self.env['ab_sales_backend']._check_store(store_id)
        values = self._validate_new_customer_payload(phone=phone, name=name, address=address)
        existing = self.pos_customer_lookup(phone=values['phone'], store_id=store.id)
        if existing['status'] == 'found':
            return existing
        customer = self.env['ab_customer'].create({
            'code': 'N' + uuid.uuid4().hex[:15],
            'name': values['name'], 'mobile_phone': values['phone'],
            'address': values['address'], 'default_store_id': store.id,
        })
        return {'status': 'created', 'customer': self._customer_payload(customer)}


class NativeSalesUI(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def pos_store_status(self, store_id=None):
        sid = store_id.id if isinstance(store_id, models.BaseModel) else store_id
        if self.env['ab_sales_backend']._is_native(sid):
            self.env['ab_sales_backend']._check_store(sid)
            return True
        return super().pos_store_status(store_id=store_id)

    @api.model
    def _inventory_balance_by_serial(self, product_serials, store_id=None):
        if self.env['ab_sales_backend']._is_native(store_id):
            products = self.env['ab_product'].search([('eplus_serial', 'in', product_serials)])
            balances = self.env['ab_sales_pos_api'].pos_refresh_pos_balances(store_id, products.ids)
            return {p.eplus_serial: balances.get(p.id, 0) for p in products}
        return super()._inventory_balance_by_serial(product_serials, store_id=store_id)

    @api.model
    def _inventory_total_and_pos_balances_by_serial(self, product_serials, store_id=None):
        if self.env['ab_sales_backend']._is_native(store_id):
            balances = self._inventory_balance_by_serial(product_serials, store_id=store_id)
            return balances, balances
        return super()._inventory_total_and_pos_balances_by_serial(product_serials, store_id=store_id)

    @api.model
    def search_products(self, query='', limit=60, has_balance=True, has_pos_balance=False,
                        header_id=None, store_id=None, customer_phone=None, item_type='all'):
        sid = self._resolve_store_id(header_id=header_id, store_id=store_id)
        if not self.env['ab_sales_backend']._is_native(sid):
            return super().search_products(query=query, limit=limit, has_balance=has_balance,
                has_pos_balance=has_pos_balance, header_id=header_id, store_id=store_id,
                customer_phone=customer_phone, item_type=item_type)
        self.env['ab_sales_backend']._check_store(sid)
        limit = max(1, min(120, int(limit)))
        domain = fields.Domain('active', '=', True)
        if item_type in ('medicine', 'non_medicine'):
            domain &= fields.Domain('is_medicine', '=', item_type == 'medicine')
        if query.strip():
            term = query.strip().replace('*', '%')
            domain &= fields.Domain('name', 'ilike', term) | fields.Domain('code', 'ilike', term) | fields.Domain('barcode_ids.name', 'ilike', term)
        candidates = self.env['ab_product'].search(domain, order='name')
        balances = self.env['ab_sales_pos_api'].pos_refresh_pos_balances(sid, candidates.ids)
        if has_balance or has_pos_balance:
            candidates = candidates.filtered(lambda p: balances.get(p.id, 0) > 0 or (query and p.is_service))
        products = candidates[:limit]
        rows = products.read(self._safe_fields('ab_product', ['name', 'product_card_name', 'code', 'is_service',
            'default_price', 'is_priced', 'is_medicine', 'allow_sell_fraction', 'eplus_serial',
            'uom_id', 'uom_category_id', 'only_default_sales_uom']))
        by_id = {p.id: p for p in products}
        for row in rows:
            product = by_id[row['id']]
            balance = balances.get(product.id, 0)
            row.update(balance=balance, pos_balance=balance, has_balance=balance > 0,
                has_pos_balance=balance > 0, uom_factor=product.uom_id.factor,
                default_uom_factor=product.uom_id.factor, customer_order_count_3m=0,
                is_top_customer=False, branch_order_count_30d=0, is_top_branch=False,
                is_pinned=False, rank_source='')
        return rows

    @api.model
    def _bill_wizard_header_payload(self, header, record_type='sale'):
        result = super()._bill_wizard_header_payload(header, record_type=record_type)
        if record_type == 'sale' and header.native_backend:
            result['can_return'] = header.status == 'saved'
        return result

    @api.model
    def _bill_wizard_header_serial_text(self, header, record_type='sale'):
        if record_type == 'sale' and header.native_backend:
            return 'N-%s' % header.id
        return super()._bill_wizard_header_serial_text(header, record_type=record_type)

    @api.model
    def _bill_wizard_receipt_total_value(self, header, record_type='sale', fallback_total=0.0):
        if record_type == 'sale' and header.native_posted:
            return header.native_totals['total_bill_net']
        if record_type == 'return' and header.native_posted:
            return header.native_refund
        return super()._bill_wizard_receipt_total_value(header, record_type=record_type, fallback_total=fallback_total)
