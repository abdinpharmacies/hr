import math
from datetime import timedelta
from contextvars import ContextVar

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_ORDER = ContextVar('ab_crm_channel_order_mutation', default=False)


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
    delivery_address = fields.Text()
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
        self.ensure_one()
        self.check_access('write')
        session, stores = self.conversation_id._owned()
        self.lock_for_update()
        self.invalidate_recordset(['state', 'store_id', 'revision', 'edit_version'])
        if self.store_id and self.store_id not in stores:
            raise AccessError(_('The fulfillment branch is not permitted.'))
        if draft and self.state != 'draft':
            raise UserError(_('Reopen the order before editing an accepted revision.'))
        return session, stores

    def _change(self, values):
        token = _ORDER.set(True)
        try:
            return self.write(values)
        finally:
            _ORDER.reset(token)

    def _audit(self, action, values):
        self.ensure_one()
        session = self.conversation_id._workspace_actor()
        token = _ORDER.set(True)
        try:
            self.env['ab_crm_channel_order_audit'].sudo().create(
                {
                    'order_id': self.id,
                    'action': action,
                    'revision': self.revision,
                    'actor_id': self.env.uid,
                    'employee_id': session.employee_id.id,
                    'at': fields.Datetime.now(),
                    'values': values,
                }
            )
        finally:
            _ORDER.reset(token)

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        allowed = {
            'conversation_id',
            'name',
            'store_id',
            'delivery_address',
            'delivery_notes',
            'line_ids',
        }
        for values in values_list:
            if values.keys() - allowed:
                raise AccessError(_('Order evidence is managed by workflow actions.'))
            conversation = (
                self.env['ab_crm_conversation']
                .browse(values.get('conversation_id'))
                .exists()
            )
            conversation.ensure_one()
            session, stores = conversation._owned()
            if values.get('store_id') and values['store_id'] not in stores.ids:
                raise AccessError(_('The fulfillment branch is not permitted.'))
            prepared.append(
                dict(
                    values,
                    state='draft',
                    revision=1,
                    accepted_by=False,
                    accepted_employee_id=False,
                    accepted_at=False,
                    confirmation=False,
                    customer_id=conversation.customer_id.id,
                    channel_id=conversation.channel_id.id,
                    customer_name=(
                        conversation._customer_display_name()
                        if conversation.customer_id
                        else False
                    ),
                    delivery_address=values.get(
                        'delivery_address', conversation.customer_id.address or ''
                    ),
                    phone=conversation.confirmed_phone or False,
                )
            )
        records = super(
            Order,
            self.with_context(
                {
                    k: v
                    for k, v in self.env.context.items()
                    if not k.startswith('default_')
                }
            ),
        ).create(prepared)
        for record in records:
            record._audit('created', {'conversation_id': record.conversation_id.id})
        return records

    def write(self, values):
        if _ORDER.get():
            return super().write(values)
        if values.keys() - {
            'name',
            'store_id',
            'delivery_address',
            'delivery_notes',
            'confirmation',
            'line_ids',
        }:
            raise AccessError(_('Order evidence is managed by workflow actions.'))
        for record in self:
            session, stores = record._authorize(draft=True)
            if values.get('store_id') and values['store_id'] not in stores.ids:
                raise AccessError(_('The fulfillment branch is not permitted.'))
        if 'store_id' in values and any(
            record.line_ids.filtered('active')
            and record.store_id.id != values['store_id']
            for record in self
        ):
            raise UserError(_('Confirm branch recalculation before saving.'))
        for record in self:
            super(Order, record).write(
                dict(values, edit_version=record.edit_version + 1)
            )
        return True

    def unlink(self):
        raise UserError(_('Cancel orders instead of deleting them.'))

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
        session, stores = self._authorize(draft=True)
        self._refresh_customer()
        if (
            not self.store_id
            or not self.confirmation
            or not self.confirmation.strip()
            or not self.line_ids.filtered('active')
        ):
            raise UserError(
                _(
                    'Acceptance requires a branch, valid order lines and customer confirmation.'
                )
            )
        self.line_ids.filtered('active')._validate_values()
        self._change(
            {
                'state': 'accepted',
                'edit_version': self.edit_version + 1,
                'accepted_by': self.env.uid,
                'accepted_employee_id': session.employee_id.id,
                'accepted_at': fields.Datetime.now(),
            }
        )
        self._audit('accepted', self._snapshot())
        return True

    def action_reopen(self, reason):
        self._authorize()
        if (
            self.state not in ('accepted', 'closed')
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise UserError(
                _('Provide a reason to reopen an accepted or closed order.')
            )
        self._audit('reopened', {'reason': reason, 'snapshot': self._snapshot()})
        self._change(
            {
                'state': 'draft',
                'revision': self.revision + 1,
                'edit_version': self.edit_version + 1,
                'confirmation': False,
                'accepted_by': False,
                'accepted_employee_id': False,
                'accepted_at': False,
            }
        )
        self._refresh_customer()
        return True

    def action_close(self):
        self._authorize()
        if self.state != 'accepted':
            raise UserError(_('Only accepted orders can be closed.'))
        self._audit('closed', self._snapshot())
        self._change({'state': 'closed', 'edit_version': self.edit_version + 1})
        return True

    def action_cancel(self, reason):
        self._authorize()
        if (
            self.state == 'cancelled'
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise UserError(_('Provide a reason to cancel the order.'))
        self._audit('cancelled', {'reason': reason, 'snapshot': self._snapshot()})
        self._change({'state': 'cancelled', 'edit_version': self.edit_version + 1})
        return True

    def workspace_data(self):
        self.ensure_one()
        self.check_access('read')
        session, stores = self.conversation_id._workspace_scope()
        if self.state == 'draft':
            self._authorize(draft=True)
            self._refresh_customer()
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
        self.ensure_one()
        if self.state == 'draft':
            conversation = self.conversation_id
            values = {
                'customer_id': conversation.customer_id.id,
                'customer_name': (
                    conversation._customer_display_name()
                    if conversation.customer_id
                    else False
                ),
                'phone': conversation.confirmed_phone or conversation.customer_id.phone,
                'delivery_address': conversation.customer_id.address,
            }
            empty = {
                key: value for key, value in values.items() if value and not self[key]
            }
            if empty:
                self._change(dict(empty, edit_version=self.edit_version + 1))

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
        self._authorize(draft=True)
        if edit_version != self.edit_version:
            raise UserError(
                _('This order changed in another window. Reopen it before saving.')
            )
        if not isinstance(values, dict) or values.keys() - {
            'store_id',
            'delivery_address',
            'delivery_notes',
            'confirmation',
        }:
            raise AccessError(_('Order evidence is managed by workflow actions.'))
        if not isinstance(lines, list) or len(lines) > 200:
            raise ValidationError(_('Invalid order lines.'))
        store_id = values.get('store_id', self.store_id.id)
        store = self._branch(store_id) if store_id else False
        branch_changed = bool(self.store_id and store != self.store_id)
        if branch_changed and self.line_ids.filtered('active') and not reprice:
            raise UserError(_('Confirm branch recalculation before saving.'))
        if lines and not store:
            raise UserError(_('Select a fulfillment branch first.'))
        with self.env.cr.savepoint():
            old_store = self.store_id.id
            self._change(dict(values, edit_version=self.edit_version + 1))
            kept = self.env['ab_crm_channel_order_line']
            seen = set()
            for row in lines:
                if not isinstance(row, dict) or row.keys() - {
                    'id',
                    'product_id',
                    'uom_id',
                    'quantity',
                    'price',
                }:
                    raise ValidationError(_('Invalid order lines.'))
                line = self.line_ids.filtered(
                    lambda r: r.id == row.get('id') and r.active
                )
                if row.get('id') and (not line or line.id in seen):
                    raise AccessError(_('Invalid order lines.'))
                seen.add(line.id)
                product = (
                    line.product_id
                    if line
                    else self.env['ab_product'].browse(row.get('product_id')).exists()
                )
                product.ensure_one()
                product.check_access('read')
                if line and product.id != row.get('product_id'):
                    raise AccessError(
                        _('Order line ownership and product cannot be changed.')
                    )
                unit = self.env['ab_product_uom'].browse(row.get('uom_id')).exists()
                unit.ensure_one()
                unit.check_access('read')
                price = row.get('price')
                if branch_changed:
                    price = (
                        self.env['ab_sales_pos_api']._store_default_price(
                            store.id, product
                        )
                        * unit.factor
                        / (product.uom_id.factor or 1)
                    )
                line_values = {
                    'uom_id': unit.id,
                    'quantity': row.get('quantity'),
                    'price': price,
                }
                if line:
                    line.write(line_values)
                else:
                    line = self.env['ab_crm_channel_order_line'].create(
                        dict(line_values, order_id=self.id, product_id=product.id)
                    )
                kept |= line
            (self.line_ids.filtered('active') - kept).write({'active': False})
            kept._validate_values()
            if branch_changed:
                self._audit('branch_changed', {'old': old_store, 'new': store.id})
            self._refresh_customer()
            if accept:
                self.action_accept()
            return self.workspace_data()

    def action_add_product(self, product_id):
        self._authorize(draft=True)
        if not self.store_id:
            raise UserError(_('Select a fulfillment branch first.'))
        product = self.env['ab_product'].browse(product_id).exists()
        product.ensure_one()
        product.check_access('read')
        price = self.env['ab_sales_pos_api']._store_default_price(
            self.store_id.id, product
        )
        return (
            self.env['ab_crm_channel_order_line']
            .create(
                {
                    'order_id': self.id,
                    'product_id': product.id,
                    'uom_id': product.uom_id.id,
                    'quantity': 1,
                    'price': price,
                }
            )
            .id
        )


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
        for values in values_list:
            self.env['ab_crm_channel_order'].browse(values.get('order_id'))._authorize(
                draft=True
            )
        records = super().create(values_list)
        for order in records.order_id:
            order._change({'edit_version': order.edit_version + 1})
        for line in records:
            line.order_id._audit(
                'line_added',
                {
                    'line_id': line.id,
                    'price': line.price,
                    'quantity': line.quantity,
                    'product_id': line.product_id.id,
                },
            )
        return records

    def write(self, values):
        if values.keys() - {'uom_id', 'quantity', 'price', 'active'}:
            raise AccessError(_('Order line ownership and product cannot be changed.'))
        for line in self:
            line.check_access('write')
            line.order_id._authorize(draft=True)
            before = {
                key: line[key].id if key == 'uom_id' else line[key] for key in values
            }
            changed = {
                key: value for key, value in values.items() if before[key] != value
            }
            if changed:
                line.order_id._audit(
                    'line_changed',
                    {
                        'line_id': line.id,
                        'old': {key: before[key] for key in changed},
                        'new': changed,
                    },
                )
        result = super().write(values)
        for order in self.order_id:
            order._change({'edit_version': order.edit_version + 1})
        return result

    def unlink(self):
        raise UserError(_('Archive order lines instead of deleting them.'))


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
        if not _ORDER.get():
            raise AccessError(_('Audit records are managed by workflow actions.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Audit records cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Audit records cannot be deleted.'))
