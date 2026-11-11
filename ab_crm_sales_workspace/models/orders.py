from .workspace import display_phone
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Order(models.Model):
    _name = 'ab_crm_channel_order'
    _description = 'Channel Order'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: _('New Order'), required=True)
    conversation_id = fields.Many2one(
        'ab_crm_conversation', required=True, ondelete='restrict', readonly=True
    )
    branch_id = fields.Many2one(related='conversation_id.branch_id', store=True)
    company_id = fields.Many2one(related='conversation_id.company_id', store=True)
    channel_id = fields.Many2one(
        'ab_crm_channel', required=True, readonly=True, ondelete='restrict'
    )
    customer_id = fields.Many2one('ab_crm_customer', ondelete='restrict', readonly=True)
    customer_name = fields.Char(readonly=True)
    delivery_location_message_id = fields.Many2one(
        'ab_crm_message', readonly=True, copy=False, ondelete='restrict',
        string='Delivery Location Message',
    )
    delivery_address = fields.Text()
    delivery_location_snapshot = fields.Json(readonly=True, copy=False)
    edit_version = fields.Integer(default=1, readonly=True)
    phone = fields.Char(readonly=True)
    store_id = fields.Many2one(
        'ab_store', ondelete='restrict', string='Fulfillment Branch'
    )
    delivery_notes = fields.Text()
    confirmation = fields.Text(string='Customer Confirmation')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('accepted', 'Accepted'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        readonly=True,
    )
    revision = fields.Integer(default=1, readonly=True)
    accepted_by = fields.Many2one('res.users', readonly=True)
    accepted_employee_id = fields.Many2one('ab_hr_employee', readonly=True)
    accepted_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many('ab_crm_channel_order_line', 'order_id')
    audit_ids = fields.One2many('ab_crm_channel_order_audit', 'order_id', readonly=True)
    total = fields.Float(compute='_compute_total', digits=(16, 2))

    @api.depends('line_ids.quantity', 'line_ids.price', 'line_ids.active')
    def _compute_total(self):
        for record in self:
            record.total = sum(
                line.quantity * line.price for line in record.line_ids if line.active
            )

    def _authorize(self, draft=False):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def _change(self, values):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def _audit(self, action, values):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def write(self, values):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def unlink(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def _snapshot(self):
        self.ensure_one()
        return {
            'customer_id': self.customer_id.id,
            'customer_name': self.customer_name,
            'phone': self.phone,
            'store_id': self.store_id.id,
            'channel_id': self.channel_id.id,
            'conversation_id': self.conversation_id.id,
            'confirmation': self.confirmation,
            'delivery_notes': self.delivery_notes,
            'delivery_address': self.delivery_address,
            'delivery_location_message_id': self.delivery_location_message_id.id or False,
            'delivery_location': self.delivery_location_snapshot or (self.delivery_location_message_id._location_data(original=True) if self.delivery_location_message_id else False),
            'lines': [
                {
                    'id': line.id,
                    'product_id': line.product_id.id,
                    'product': line.product_id.display_name
                    or line.product_id.product_card_id.name,
                    'uom_id': line.uom_id.id,
                    'uom': line.uom_id.name,
                    'quantity': line.quantity,
                    'price': line.price,
                }
                for line in self.line_ids
                if line.active
            ],
        }

    def action_accept(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def action_reopen(self, reason):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def action_close(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def action_cancel(self, reason):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def workspace_data(self):
        self.ensure_one()
        self.check_access('read')
        session, stores = self.conversation_id._workspace_scope()
        return dict(
            self._snapshot(),
            id=self.id,
            name=self.name,
            state=self.state,
            revision=self.revision,
            total=self.total,
            edit_version=self.edit_version,
            provider=self.channel_id.provider,
            identified=bool(self.customer_id and self.phone),
            display_phone=display_phone(self.phone, self.company_id.country_id.code),
            phone_options=self.customer_id._directory_data()['phones'] if self.customer_id else [],
            selected_phone_id=self.customer_id.phone_ids.filtered(lambda p: p.number == self.phone)[:1].id,
            stores=[
                {'id': store.id, 'name': store.name, 'code': store.code}
                for store in stores
            ],
            units={
                line.id: [
                    {'id': unit.id, 'name': unit.name, 'factor': unit.factor}
                    for unit in self.env['ab_product_uom'].search(
                        [
                            ('category_id', '=', line.product_id.uom_category_id.id),
                            ('active', '=', True),
                        ]
                        + (
                            [('id', '=', line.product_id.uom_id.id)]
                            if line.product_id.only_default_sales_uom
                            else []
                        )
                    )
                ]
                for line in self.line_ids
            },
            audits=[
                {
                    'id': a.id,
                    'action': a.action,
                    'revision': a.revision,
                    'actor': a.actor_id.display_name,
                    'at': fields.Datetime.to_string(a.at),
                    'values': a.values,
                }
                for a in self.audit_ids
            ],
        )

    def _refresh_customer(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def _branch(self, store_id):
        session, stores = self._authorize(draft=True)
        store = stores.filtered(lambda record: record.id == store_id)
        if not store:
            raise AccessError(_('The fulfillment branch is not permitted.'))
        return store

    def _product_data(self, products, store):
        inventory = (
            self.env['ab_sales_inventory']
            .sudo()
            .search(
                [
                    ('store_id', '=', store.id),
                    ('product_eplus_serial', 'in', products.mapped('eplus_serial')),
                ]
            )
        )
        balances = {row.product_eplus_serial: row for row in inventory}
        result = []
        for product in products:
            product.check_access('read')
            units = self.env['ab_product_uom'].search(
                [
                    ('category_id', '=', product.uom_category_id.id),
                    ('active', '=', True),
                ]
                + (
                    [('id', '=', product.uom_id.id)]
                    if product.only_default_sales_uom
                    else []
                )
            )
            balance = (
                balances.get(product.eplus_serial) if product.eplus_serial else False
            )
            updated = balance.write_date if balance else False
            result.append(
                {
                    'id': product.id,
                    'name': product.display_name or product.product_card_id.name,
                    'code': product.code or '',
                    'medicine': product.is_medicine,
                    'price': self.env['ab_sales_pos_api']._store_default_price(
                        store.id, product
                    ),
                    'uom_id': product.uom_id.id,
                    'factor': product.uom_id.factor,
                    'units': [
                        {'id': u.id, 'name': u.name, 'factor': u.factor} for u in units
                    ],
                    'balance': balance.balance if balance else None,
                    'balance_at': fields.Datetime.to_string(updated),
                    'balance_state': (
                        'unavailable'
                        if not balance
                        else (
                            'stale'
                            if not updated
                            or updated < fields.Datetime.now() - timedelta(minutes=15)
                            else 'cached'
                        )
                    ),
                }
            )
        return result

    def search_products(
        self, query='', store_id=False, category='all', minimum=False, maximum=False
    ):
        store = self._branch(store_id or self.store_id.id)
        domain = [('active', '=', True), ('allow_sale', '=', True)]
        if query:
            domain += [
                '|',
                '|',
                '|',
                ('product_card_id.name', 'ilike', str(query)[:100]),
                ('product_search', 'ilike', str(query)[:100]),
                ('code', 'ilike', str(query)[:100]),
                ('barcode_ids.name', '=', str(query)[:100]),
            ]
        if category in ('medicine', 'non_medicine'):
            domain.append(('is_medicine', '=', category == 'medicine'))
        products = self.env['ab_product'].search(domain, limit=100)
        result = self._product_data(products, store)
        return [
            dict(
                row,
                barcode_match=bool(
                    query
                    and products.filtered(
                        lambda product: product.id == row['id']
                        and str(query) in product.barcode_ids.mapped('name')
                    )
                ),
            )
            for row in result
            if (minimum is False or row['price'] >= float(minimum))
            and (maximum is False or row['price'] <= float(maximum))
        ][:30]

    def preview_branch(self, store_id, product_ids):
        store = self._branch(store_id)
        products = self.env['ab_product'].browse(product_ids).exists()
        products.check_access('read')
        if len(products) != len(set(product_ids)) or any(
            not p.active or not p.allow_sale for p in products
        ):
            raise ValidationError(
                _(
                    'Use an active sale product, valid unit, positive quantity and nonnegative price.'
                )
            )
        return self._product_data(products, store)

    def action_save_draft(
        self, values, lines, edit_version, reprice=False, accept=False
    ):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def action_add_product(self, product_id):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))


class Line(models.Model):
    _name = 'ab_crm_channel_order_line'
    _description = 'Channel Order Line'

    order_id = fields.Many2one(
        'ab_crm_channel_order', required=True, ondelete='restrict'
    )
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_product_uom', required=True, ondelete='restrict')
    quantity = fields.Float(default=1, required=True, digits=(16, 6))
    price = fields.Float(required=True, digits=(16, 2))
    active = fields.Boolean(default=True)

    @api.constrains('product_id', 'uom_id', 'quantity', 'price', 'active')
    def _validate_values(self):
        for line in self:
            line.product_id.check_access('read')
            line.uom_id.check_access('read')
            if not line.active:
                continue
            if (
                not line.product_id.active
                or not line.product_id.allow_sale
                or not line.uom_id.active
                or line.uom_id.category_id != line.product_id.uom_category_id
                or not math.isfinite(line.uom_id.factor)
                or line.uom_id.factor <= 0
                or not math.isfinite(line.quantity)
                or line.quantity <= 0
                or not math.isfinite(line.price)
                or line.price < 0
            ):
                raise ValidationError(
                    _(
                        'Use an active sale product, valid unit, positive quantity and nonnegative price.'
                    )
                )
            if (
                line.product_id.only_default_sales_uom
                and line.uom_id != line.product_id.uom_id
            ):
                raise ValidationError(
                    _('This product requires its default sales unit.')
                )
            if not line.product_id.allow_sell_fraction and line.quantity != int(
                line.quantity
            ):
                raise ValidationError(_('This product requires a whole quantity.'))

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def write(self, values):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def unlink(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))


class Audit(models.Model):
    _name = 'ab_crm_channel_order_audit'
    _description = 'Channel Order Audit'
    _order = 'id'

    order_id = fields.Many2one(
        'ab_crm_channel_order', required=True, ondelete='restrict'
    )
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    action = fields.Char(required=True)
    revision = fields.Integer(required=True)
    actor_id = fields.Many2one('res.users', required=True)
    employee_id = fields.Many2one(
        'ab_hr_employee',
        required=True,
        groups='ab_crm_core.group_manager,base.group_system',
    )
    at = fields.Datetime(required=True)
    values = fields.Json(required=True)

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def write(self, values):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))

    def unlink(self):
        raise AccessError(_('Legacy chatter orders are read-only. Use Sales to create orders.'))
