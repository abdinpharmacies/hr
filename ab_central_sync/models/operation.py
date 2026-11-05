"""Durable transport journal. Business effects stay in the existing sales models."""
import hashlib
import json
import logging
import uuid
from datetime import timedelta

import requests
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class CentralOperation(models.Model):
    _name = 'ab_central_sync_operation'
    _description = 'Central Synchronization Operation'
    _order = 'id desc'
    _rec_name = 'token'

    active = fields.Boolean(default=True)
    token = fields.Char(required=True, readonly=True, index=True)
    origin = fields.Char(required=True, readonly=True, index=True)
    direction = fields.Selection([('out', 'Outgoing'), ('in', 'Incoming')], required=True, readonly=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    serial = fields.Integer(required=True, readonly=True)
    kind = fields.Selection([(x, x.replace('_', ' ').title()) for x in
                             ('sale', 'sale_settle', 'return', 'return_settle', 'sale_cancel')], required=True, readonly=True)
    state = fields.Selection([(x, x.title()) for x in
                              ('queued', 'processing', 'accepted', 'retryable', 'uncertain', 'rejected')], default='queued', readonly=True)
    payload = fields.Json(required=True, readonly=True)
    payload_hash = fields.Char(required=True, readonly=True)
    result = fields.Json(readonly=True)
    accepted_at = fields.Datetime(readonly=True)
    attempts = fields.Integer(readonly=True)
    next_retry = fields.Datetime(readonly=True)
    error = fields.Text(readonly=True)
    history = fields.Json(readonly=True)
    reconciliation = fields.Json(readonly=True)
    source_document = fields.Char(readonly=True, index=True)
    document_model = fields.Char(readonly=True)
    document_id = fields.Integer(readonly=True)
    resolution_reason = fields.Text(string='Reconciliation Reason', readonly=True, copy=False)
    resolved_by_id = fields.Many2one('res.users', string='Reconciled By', readonly=True, copy=False)
    resolved_at = fields.Datetime(string='Reconciled At', readonly=True, copy=False)
    resolution_evidence = fields.Json(string='Reconciliation Evidence', readonly=True, copy=False)
    _business_event = models.Constraint('UNIQUE(direction, origin, store_id, kind, source_document)', 'This business event already has a synchronization operation.')
    _identity = models.Constraint('UNIQUE(direction, origin, token)', 'Operation identity already exists.')
    _serial = models.Constraint('UNIQUE(direction, origin, store_id, serial)', 'Process serial already exists.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('The synchronization service maintains the journal.'))
        vals_list = [dict(vals, source_document=vals.get('payload', {}).get('source_document')) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su or {'token', 'origin', 'direction', 'store_id', 'serial', 'kind', 'payload', 'payload_hash', 'source_document'} & vals.keys():
            raise AccessError(_('Operation payloads and identities are immutable.'))
        return super().write(vals)

    def action_archive(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        if any(operation.state != 'accepted' for operation in self):
            raise ValidationError(_('Only accepted operations can be archived.'))
        return super(CentralOperation, self.sudo()).action_archive()

    def action_unarchive(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        return super(CentralOperation, self.sudo()).action_unarchive()

    def unlink(self):
        raise AccessError(_('Archive synchronization operations instead of deleting them.'))

    @api.model
    def _param(self, key, default=False):
        if key == 'role':
            return 'central'
        return self.env['ir.config_parameter'].sudo().get_param('ab_central_sync.' + key, default)

    @api.model
    def _uses_central(self, store, role=None):
        if not store or (role and role != 'central'):
            return False
        from .sales import REPLAY_ORIGIN
        origin = REPLAY_ORIGIN.get()
        return bool((origin and origin.get('inventory_store_id') == store.id) or self.sudo().search_count(
            fields.Domain('direction', '=', 'in') & fields.Domain('store_id', '=', store.id), limit=1))


    def action_retry(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        # A stale Retry click must not undo acceptance or reconciliation.
        if self._param('role') == 'central':
            self.store_id._lock_stock_scope()
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        for operation in self:
            if operation.state != 'accepted':
                operation.sudo().write({'state': 'retryable', 'next_retry': False, 'error': False})
        return True


    @api.model
    def _central_stock_snapshot(self, store, origin, after, codes=None):
        if not self.env.su or self._param('role') != 'central' or type(after) is not int or after < 0:
            raise AccessError(_('Invalid stock snapshot request.'))
        # Caller holds the same store lock as posting. Balance and accepted watermark
        # therefore describe a single ledger state, even if acknowledgment was lost.
        lock = self.env['ab_stock_integration_lock'].search(fields.Domain('store_id', '=', store.id), limit=1)
        operations = self.with_context(active_test=False).search(fields.Domain('direction', '=', 'in')
            & fields.Domain('origin', '=', origin) & fields.Domain('store_id', '=', store.id)
            & fields.Domain('state', '=', 'accepted'), order='serial')
        watermark = 0
        accepted_serials = operations.mapped('serial')
        for serial in accepted_serials:
            if serial != watermark + 1:
                break
            watermark = serial
        stocked = self.env['ab_inventory']._read_group(
            fields.Domain('store_id', '=', store.id), ['product_id'], [])
        domain = fields.Domain('id', '>', after) & fields.Domain('id', 'in', [product.id for product, in stocked if product])
        if codes is not None:
            if not isinstance(codes, list) or len(codes) > 200 or any(not isinstance(code, str) for code in codes):
                raise ValidationError(_('Invalid product snapshot request.'))
            domain &= fields.Domain('code', 'in', codes)
        products = self.env['ab_product'].with_context(active_test=False).search(domain, order='id', limit=501)
        rows = []
        for product in products[:500]:
            batches = self.env['ab_sales_stock_allocation']._source_rows(store, product) if not product.is_service and product.active else []
            for batch in batches:
                batch['expiry'] = fields.Date.to_string(batch['expiry']) if batch['expiry'] else False
            rows.append({'code': product.code, 'balance': sum(row['qty'] for row in batches) / (float(product._stock_unit_factor(product.uom_id)) if batches else 1),
                         'default_price': product.default_price, 'batches': batches})
        return {'version': 2, 'stock_basis': 'product_uom_reference', 'origin': origin, 'store': store.code, 'revision': lock.revision,
                'watermark': watermark, 'accepted_serials': [s for s in accepted_serials if s > watermark], 'at': fields.Datetime.to_string(fields.Datetime.now()),
                'products': rows, 'next': products[499].id if len(products) > 500 else None}
