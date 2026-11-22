import hashlib
from contextvars import ContextVar
from uuid import UUID, uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from ..protocol import fingerprint

_CAPTURE = ContextVar('ab_website_capture', default=False)


class Endpoint(models.Model):
    _name = 'ab_storefront_callcenter_endpoint'
    _description = 'Callcenter Endpoint'
    _check_company_auto = True

    name = fields.Char(required=True)
    source = fields.Char(required=True, default=lambda self: str(uuid4()), copy=False)
    website_id = fields.Many2one(
        'website', ondelete='restrict', check_company=True
    )
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    service_user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    enabled = fields.Boolean(default=False)
    cutoff = fields.Datetime(required=True, default=fields.Datetime.now)
    _source_unique = models.Constraint('UNIQUE(source)', 'Source must be unique.')
    _website_unique = models.Constraint(
        'UNIQUE(website_id)', 'Website endpoint already exists.'
    )

    @api.onchange('website_id')
    def _onchange_website_id(self):
        self.company_id = self.website_id.company_id

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            website = self.env['website'].browse(values.get('website_id')).exists()
            if not website:
                raise ValidationError(_('Select a website for a new endpoint.'))
            prepared.append(dict(values, company_id=website.company_id.id))
        return super().create(prepared)

    @api.constrains('enabled', 'website_id')
    def _check_enabled_website(self):
        for record in self:
            if record.enabled and not record.website_id:
                raise ValidationError(_('An enabled endpoint requires a website.'))

    @api.constrains('service_user_id', 'website_id', 'source')
    def _check_service(self):
        for record in self:
            try:
                if str(UUID(record.source)) != record.source:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValidationError(_('Invalid website source.')) from None
            user = record.service_user_id
            if (
                not user.has_group('ab_storefront_callcenter_adapter.group_service')
                or user.has_group('base.group_system')
                or user.has_group('sales_team.group_sale_salesman')
                or record.company_id not in user.company_ids
            ):
                raise ValidationError(_('Use a dedicated callcenter exchange user.'))

    def write(self, values):
        if {'source', 'company_id'} & values.keys():
            raise AccessError(_('Endpoint identity is immutable.'))
        if 'website_id' in values and (
            values['website_id']
            or not self.env.user.has_group('base.group_system')
            or self.filtered('enabled')
        ):
            raise AccessError(_('Endpoint identity is immutable.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Disable the endpoint instead of deleting it.'))


class Unit(models.Model):
    _inherit = 'uom.uom'

    ab_callcenter_code = fields.Char(
        string='Callcenter Unit Code', groups='base.group_system'
    )


class Order(models.Model):
    _inherit = 'sale.order'

    ab_callcenter_uuid = fields.Char(copy=False, readonly=True, index=True)
    ab_callcenter_revision = fields.Integer(copy=False, readonly=True)
    ab_callcenter_endpoint_id = fields.Many2one(
        'ab_storefront_callcenter_endpoint', copy=False, readonly=True
    )
    ab_callcenter_capability_hash = fields.Char(copy=False, groups='base.group_system')
    ab_callcenter_capability_expires = fields.Datetime(
        copy=False, groups='base.group_system'
    )
    ab_callcenter_owner_hash = fields.Char(copy=False, groups='base.group_system')
    _callcenter_uuid_unique = models.Constraint(
        'UNIQUE(ab_callcenter_uuid)', 'Order UUID must be unique.'
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get() and any(
            any(key.startswith('ab_callcenter_') for key in values)
            for values in values_list
        ):
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if (
            any(key.startswith('ab_callcenter_') for key in values)
            and not _CAPTURE.get()
        ):
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if (
                order.state == 'sale'
                and order.website_id
                and not order.ab_prescription_order_ids
                and not order.ab_callcenter_uuid
            ):
                endpoint = (
                    self.env['ab_storefront_callcenter_endpoint']
                    .sudo()
                    .search(
                        [
                            ('website_id', '=', order.website_id.id),
                            ('enabled', '=', True),
                            ('cutoff', '<=', order.create_date),
                        ],
                        limit=1,
                    )
                )
                if endpoint:
                    order._ab_callcenter_capture(endpoint)
        return result

    def _ab_callcenter_capture(self, endpoint):
        self.ensure_one()
        self.check_access('write')
        if (
            endpoint.website_id != self.website_id
            or endpoint.company_id != self.company_id
        ):
            raise AccessError(_('Invalid website source.'))
        self = self.sudo().with_context(allowed_company_ids=self.company_id.ids)
        self.lock_for_update()
        self.invalidate_recordset(['ab_callcenter_uuid'])
        if self.ab_callcenter_uuid:
            return
        guard = _CAPTURE.set(True)
        try:
            self.sudo().write(
                {
                    'ab_callcenter_uuid': str(uuid4()),
                    'ab_callcenter_endpoint_id': endpoint.id,
                    'ab_callcenter_owner_hash': self.ab_checkout_submission_id.owner_hash
                    or False,
                }
            )
            self._ab_callcenter_event('order', self._ab_callcenter_snapshot())
        finally:
            _CAPTURE.reset(guard)

    def _ab_callcenter_snapshot(self):
        self.ensure_one()
        shipping = self.partner_shipping_id
        lines = []
        for line in self.order_line.filtered(lambda row: not row.display_type):
            product = line.product_id.ab_product_id
            lines.append(
                {
                    'serial': str(product.eplus_serial) if product.eplus_serial else '',
                    'unit': line.product_uom_id.sudo().ab_callcenter_code or '',
                    'unit_name': line.product_uom_id.name or '',
                    'name': line.name,
                    'is_delivery': bool(line.is_delivery),
                    'quantity': line.product_uom_qty,
                    'price': line.price_unit,
                    'discount': line.discount,
                    'subtotal': line.price_subtotal,
                    'total': line.price_total,
                }
            )
        return {
            'reference': self.name,
            'public_reference': self.ab_public_reference or '',
            'customer': {
                'name': shipping.name or self.partner_id.name or '',
                'phone': shipping.phone or self.partner_id.phone or '',
                'address': shipping._display_address(without_company=False),
            },
            'notes': str(self.note or ''),
            'lines': lines,
            'currency': self.currency_id.name,
            'total': self.amount_total,
            'untaxed': self.amount_untaxed,
            'tax': self.amount_tax,
            'payments': [
                {
                    'reference': tx.reference,
                    'provider': tx.provider_id.code,
                    'method': (tx.provider_id.custom_mode if tx.provider_id.code == 'custom'
                               else tx.payment_method_id.code) or '',
                    'state': tx.state,
                    'amount': tx.amount,
                    'currency': tx.currency_id.name,
                    'provider_reference': tx.provider_reference or '',
                    'last_state_change': fields.Datetime.to_string(
                        tx.last_state_change
                    ),
                }
                for tx in self.transaction_ids
            ],
            'fulfillment': {
                'state': self.state,
                'delivery_status': self.delivery_status,
                'pickings': [
                    {
                        'reference': picking.name,
                        'state': picking.state,
                        'reservation': picking.move_ids.mapped('state'),
                    }
                    for picking in self.picking_ids
                ],
            },
        }

    def _ab_callcenter_event(self, kind, payload, event_uuid=None):
        self.ensure_one()
        if (
            not _CAPTURE.get()
            or not self.ab_callcenter_uuid
            or not self.ab_callcenter_endpoint_id.enabled
        ):
            raise AccessError(_('Website intake is disabled.'))
        self.lock_for_update()
        self.invalidate_recordset(['ab_callcenter_revision'])
        if event_uuid:
            from uuid import UUID

            try:
                if str(UUID(event_uuid)) != event_uuid:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValidationError(_('Invalid website message.')) from None
            existing = (
                self.env['ab_storefront_callcenter_event']
                .sudo()
                .search([('event_uuid', '=', event_uuid)], limit=1)
            )
            if existing:
                if (
                    existing.order_id != self
                    or existing.envelope['kind'] != kind
                    or existing.envelope['payload'] != payload
                ):
                    raise ValidationError(_('Conflicting website event.'))
                return event_uuid
        revision = self.ab_callcenter_revision + 1
        event = {
            'version': 1,
            'source': self.ab_callcenter_endpoint_id.source,
            'order_uuid': self.ab_callcenter_uuid,
            'event_uuid': event_uuid or str(uuid4()),
            'revision': revision,
            'kind': kind,
            'payload': payload,
        }
        event['fingerprint'] = fingerprint(event)
        self.env['ab_storefront_callcenter_event'].sudo().create(
            {
                'endpoint_id': self.ab_callcenter_endpoint_id.id,
                'order_id': self.id,
                'event_uuid': event['event_uuid'],
                'envelope': event,
            }
        )
        self.sudo().write({'ab_callcenter_revision': revision})
        return event['event_uuid']

    def action_ab_callcenter_publish_revision(self):
        if not (
            self.env.user.has_group('sales_team.group_sale_manager')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_('Only sales managers can publish callcenter updates.'))
        self.check_access('write')
        for order in self:
            if (
                not order.ab_callcenter_uuid
                or order.company_id not in self.env.companies
                or order.ab_callcenter_endpoint_id.sudo().website_id != order.website_id
            ):
                raise AccessError(_('Invalid website order.'))
        guard = _CAPTURE.set(True)
        try:
            for order in self:
                order.lock_for_update()
                order.invalidate_recordset()
                scoped = order.sudo().with_context(
                    allowed_company_ids=order.company_id.ids
                )
                scoped._ab_callcenter_event('order', scoped._ab_callcenter_snapshot())
        finally:
            _CAPTURE.reset(guard)
        return True


class Event(models.Model):
    _name = 'ab_storefront_callcenter_event'
    _description = 'Callcenter Outgoing Event'
    _order = 'id'

    endpoint_id = fields.Many2one(
        'ab_storefront_callcenter_endpoint', required=True, ondelete='restrict'
    )
    company_id = fields.Many2one(related='endpoint_id.company_id', store=True)
    order_id = fields.Many2one('sale.order', required=True, ondelete='restrict')
    event_uuid = fields.Char(required=True)
    envelope = fields.Json(required=True)
    acknowledged = fields.Boolean(default=False)
    _event_unique = models.Constraint('UNIQUE(event_uuid)', 'Event already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _CAPTURE.get() or set(values) - {'acknowledged'}:
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Website evidence is immutable.'))


class Reply(models.Model):
    _name = 'ab_storefront_callcenter_reply'
    _description = 'Callcenter Reply'
    _order = 'id'

    order_id = fields.Many2one('sale.order', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    token = fields.Char(required=True)
    body = fields.Text(required=True)
    _reply_unique = models.Constraint(
        'UNIQUE(order_id, token)', 'Reply already exists.'
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Website evidence is immutable.'))

    def unlink(self):
        raise AccessError(_('Website evidence is immutable.'))


class Exchange(models.AbstractModel):
    _name = 'ab_storefront_callcenter_api'
    _description = 'Callcenter Exchange'

    def _endpoint(self, source):
        user = self.env.user
        if (
            not user.active
            or not user.has_group('ab_storefront_callcenter_adapter.group_service')
            or user.has_group('base.group_system')
            or user.has_group('sales_team.group_sale_salesman')
        ):
            raise AccessError(_('Use a dedicated callcenter exchange user.'))
        endpoint = self.env['ab_storefront_callcenter_endpoint'].search(
            [
                ('source', '=', source),
                ('enabled', '=', True),
                ('service_user_id', '=', user.id),
                ('company_id', 'in', self.env.companies.ids),
            ],
            limit=1,
        )
        if not endpoint:
            raise AccessError(_('Website intake is disabled.'))
        endpoint._check_service()
        endpoint.lock_for_update()
        return endpoint

    @api.model
    def fetch_v1(self, source):
        endpoint = self._endpoint(source)
        return [
            row.envelope
            for row in self.env['ab_storefront_callcenter_event']
            .sudo()
            .search(
                [
                    ('endpoint_id', '=', endpoint.id),
                    ('acknowledged', '=', False),
                ],
                limit=50,
            )
        ]

    @api.model
    def acknowledge_v1(self, source, event_uuid, fingerprint):
        endpoint = self._endpoint(source)
        event = (
            self.env['ab_storefront_callcenter_event']
            .sudo()
            .search(
                [
                    ('endpoint_id', '=', endpoint.id),
                    ('event_uuid', '=', event_uuid),
                ],
                limit=1,
            )
        )
        if not event or event.envelope['fingerprint'] != fingerprint:
            raise ValidationError(_('Invalid website acknowledgement.'))
        guard = _CAPTURE.set(True)
        try:
            event.write({'acknowledged': True})
        finally:
            _CAPTURE.reset(guard)
        return True

    @api.model
    def receive_v1(self, source, order_uuid, token, body):
        endpoint = self._endpoint(source)
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 128
            or not isinstance(body, str)
            or not 1 <= len(body.strip()) <= 4096
        ):
            raise ValidationError(_('Invalid website reply.'))
        order = (
            self.env['sale.order']
            .sudo()
            .search(
                [
                    ('ab_callcenter_endpoint_id', '=', endpoint.id),
                    ('ab_callcenter_uuid', '=', order_uuid),
                    ('website_id', '=', endpoint.website_id.id),
                    ('company_id', '=', endpoint.company_id.id),
                ],
                limit=1,
            )
        )
        if not order:
            raise AccessError(_('Invalid website order.'))
        reply = (
            self.env['ab_storefront_callcenter_reply']
            .sudo()
            .search([('order_id', '=', order.id), ('token', '=', token)], limit=1)
        )
        if reply and reply.body != body:
            raise ValidationError(_('Conflicting website reply.'))
        guard = _CAPTURE.set(True)
        try:
            if not reply:
                self.env['ab_storefront_callcenter_reply'].sudo().create(
                    {'order_id': order.id, 'token': token, 'body': body}
                )
        finally:
            _CAPTURE.reset(guard)
        return {'reference': token}


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        return [
            *super()._get_translation_frontend_modules_name(),
            'ab_storefront_callcenter_adapter',
        ]
