import hashlib
import json
from decimal import Decimal

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .common import FINANCIAL, allocate, count_quantity, decimal, unit_factor, workflow_context


class AuditLine(models.Model):
    _name = 'ab_inventory_audit_line'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit Count Group'
    _rec_name = 'product_id'
    _order = 'product_id, id'

    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict', index=True)
    product_code = fields.Char(related='product_id.code')
    barcodes = fields.Char(compute='_compute_barcodes')
    large_unit_id = fields.Many2one(related='product_id.unit_l_id')
    medium_unit_id = fields.Many2one(related='product_id.unit_m_id')
    small_unit_id = fields.Many2one(related='product_id.unit_s_id')
    counting_revision = fields.Integer(default=1, required=True)
    physical_absence = fields.Boolean()
    group_key = fields.Char(required=True)
    exp_date = fields.Date()
    no_expiry = fields.Boolean()
    expired = fields.Boolean(compute='_compute_expired')
    comparison_price = fields.Float(digits=(16, 3))
    assigned_ids = fields.Many2many('res.users', string='Assigned Counters')
    state = fields.Selection([('new', 'New Coverage'), ('uncounted', 'Uncounted'), ('counting', 'Counting'),
                              ('counted', 'Counted'), ('invalid', 'Recount Required'),
                              ('accepted', 'Accepted'), ('excluded', 'Excluded')], default='uncounted', required=True)
    latest_attempt_id = fields.Many2one('ab_inventory_audit_count', compute='_compute_latest_attempt')
    physical_quantity = fields.Char(compute='_compute_latest_attempt')
    accepted_count_id = fields.Many2one('ab_inventory_audit_count', ondelete='restrict')
    reference_qty = fields.Float(digits=(24, 8), )
    counted_qty = fields.Float(digits=(24, 8), )
    discrepancy = fields.Float(digits=(24, 8), )
    review_reason = fields.Text()
    exclusion_reason = fields.Text()
    allocation_unresolved = fields.Boolean()
    allocation_issue = fields.Text()
    allocation_resolution = fields.Text()
    source_ids = fields.One2many('ab_inventory_audit_source', 'line_id', groups=FINANCIAL)
    count_ids = fields.One2many('ab_inventory_audit_count', 'line_id')
    posted_qty = fields.Float(digits=(24, 8), compute='_compute_stock')
    reserved_qty = fields.Float(digits=(24, 8), compute='_compute_stock')
    available_qty = fields.Float(digits=(24, 8), compute='_compute_stock')
    _key_unique = models.Constraint('UNIQUE(audit_id, group_key)', 'This count group already exists.')

    def _compute_barcodes(self):
        for line in self:
            line.barcodes = ', '.join(line.product_id.barcode_ids.mapped('name'))

    @api.depends('product_id', 'exp_date', 'comparison_price')
    def _compute_display_name(self):
        for line in self:
            line.display_name = _('Group %(group)s: %(product)s / %(expiry)s / %(price)s',
                                  group=line.id, product=line.product_id.display_name or line.product_code,
                                  expiry=str(line.exp_date or ''), price=line.comparison_price)

    def _edit(self, vals):
        relevant = {'assigned_ids', 'group_key', 'product_id', 'exp_date', 'no_expiry', 'comparison_price'}
        changed = bool(set(vals) & relevant) or vals.get('state') in ('uncounted', 'excluded')
        if changed:
            for line in self:
                super(AuditLine, line)._edit(dict(vals, counting_revision=line.counting_revision + 1))
            return True
        return super()._edit(vals)

    @api.depends('count_ids', 'count_ids.state', 'count_ids.quantity', 'accepted_count_id')
    def _compute_latest_attempt(self):
        for line in self:
            latest = line.count_ids.sorted('id', reverse=True)[:1]
            line.latest_attempt_id = latest
            counted = line.accepted_count_id or latest.filtered(lambda count: count.state not in ('active', 'cancelled'))
            line.physical_quantity = str(counted.quantity) if counted else False

    def _compute_expired(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.expired = bool(line.exp_date and line.exp_date < today)

    def _compute_stock(self):
        for audit in self.audit_id:
            audit.check_access('read')
            audit._check_branch(audit.store_id)
            selected = self.filtered(lambda item: item.audit_id == audit)
            ledger = audit._ledger(product_ids=selected.product_id.ids, group_keys=set(selected.mapped('group_key')), include_moves=False)
            for line in self.filtered(lambda item: item.audit_id == audit):
                sources = ledger.get(line.group_key, {}).get('sources', {})
                line.posted_qty = sum(item['balance'] for item in sources.values())
                line.reserved_qty = sum(item['reserved'] for item in sources.values())
                line.available_qty = line.posted_qty - line.reserved_qty

    def _authorize_count(self):
        self.ensure_one()
        self.check_access('read')
        manager = self.audit_id._authorize()
        if not manager and self.env.user not in self.assigned_ids:
            raise AccessError(_('This group is not assigned to you.'))
        if self.audit_id.state not in ('counting', 'review') or self.state in ('new', 'excluded'):
            raise ValidationError(_('This group is not open for counting.'))

    def _boundary(self, ledger=None):
        self.ensure_one()
        if ledger is None:
            ledger = self.audit_id._ledger(product_ids=self.product_id.ids,
                                           group_keys=None if self.physical_absence else {self.group_key})
        data = ledger.get(self.group_key, {})
        if self.physical_absence:
            data = {'sources': {}, 'moves': []}
            for item in ledger.values():
                if item['product_id'] == self.product_id.id:
                    data['sources'].update(item['sources'])
                    data['moves'].extend(item['moves'])
        sources = data.get('sources', {})
        product = self.product_id.sudo()
        return {'sources': {str(key): {name: value for name, value in item.items() if name != 'reserved'}
                            for key, item in sources.items()},
                'moves': data.get('moves', []),
                'units': [[unit.id, unit.factor] for unit in product.uom_ids.sorted('id')]}

    def _start(self, method='manual', batch=None, ledger=None):
        self._authorize_count()
        active = self.sudo().count_ids.filtered(lambda count: count.state == 'active')
        if active:
            if active.counter_id == self.env.user and not batch:
                return active.with_env(self.env)
            raise ValidationError(_('This group already has an active count attempt.'))
        if self.state == 'accepted':
            raise ValidationError(_('Request a recount before replacing an accepted result.'))
        attempt = self.env['ab_inventory_audit_count']._new({
            'audit_id': self.audit_id.id, 'line_id': self.id, 'counter_id': self.env.uid,
            'input_method': method, 'boundary': self._boundary(ledger),
            'export_token': batch, 'revision': self.counting_revision})
        self._edit({'state': 'counting'})
        self.audit_id._event(_('Count started'), self.product_code or '')
        return attempt

    def action_start(self, input_method='manual'):
        if input_method not in ('manual', 'barcode'):
            raise ValidationError(_('Select a supported counting method.'))
        with self.env.cr.savepoint():
            self._authorize_count()
            self.audit_id._lock()
            attempt = self._start(input_method)
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_inventory_audit_wizard',
                'view_mode': 'form', 'views': [(False, 'form')], 'name': _('Audit Workflow'), 'target': 'new',
                'context': {'default_audit_id': self.audit_id.id, 'default_line_id': self.id,
                            'default_count_id': attempt.id, 'default_operation': 'count'}}

    def action_review_wizard(self):
        self.ensure_one()
        self.audit_id._authorize(True)
        action = self.audit_id.action_workflow()
        action['context'].update(default_line_id=self.id, default_count_id=self.latest_attempt_id.id,
                                 default_operation='review')
        return action

    def _accept(self, attempt, reason):
        self.ensure_one()
        self.audit_id._authorize(True)
        if attempt.line_id != self or attempt.state != 'valid':
            raise ValidationError(_('Select a valid count attempt from this group.'))
        unresolved = self.sudo().count_ids.filtered(lambda count: count.state == 'active' or (count.state == 'invalid' and count.id > attempt.id))
        if unresolved:
            raise ValidationError(_('Resolve later invalid or active attempts before accepting this count.'))
        previous_invalid = self.sudo().count_ids.filtered(lambda count: count.state == 'invalid' and count.id < attempt.id)
        previous_invalid._edit({'state': 'superseded', 'resolution_reason': _('Resolved by an accepted recount.')})
        if self.physical_absence and attempt.counter_id == self.env.user:
            raise AccessError(_('Physical absence requires independent manager review.'))
        discrepancy = attempt.quantity - attempt.reference_qty
        if discrepancy and not reason:
            raise ValidationError(_('Document the reason for accepting a discrepancy.'))
        self._edit({'accepted_count_id': attempt.id, 'reference_qty': attempt.reference_qty,
                    'counted_qty': attempt.quantity, 'discrepancy': discrepancy,
                    'review_reason': reason, 'state': 'accepted'})
        for source in self.sudo().source_ids:
            source._edit({'allocation_qty': 0, 'reference_qty': 0})
        existing = {source.source_id.id: source for source in self.sudo().source_ids if source.source_id}
        for source_id, data in attempt.sudo().boundary['sources'].items():
            source_id = int(source_id)
            if source_id in existing:
                existing[source_id]._edit({'reference_qty': data['balance']})
            else:
                self.env['ab_inventory_audit_source']._new({
                    'audit_id': self.audit_id.id, 'line_id': self.id, 'source_id': source_id,
                    'reference_qty': data['balance']})
        sources = self.sudo().source_ids
        weights = {source.source_id.id: max(source.reference_qty, 0) for source in sources if source.source_id}
        allocations = allocate(discrepancy, weights) if discrepancy and sum(weights.values()) else {}
        for source in sources:
            source._edit({'allocation_qty': allocations.get(source.source_id.id, 0)})
        self.audit_id._revise(reason or _('Count accepted'))
        self.audit_id._event(_('Count accepted'), reason)

    def _allocation_balances(self):
        sources = self.sudo().source_ids.filtered(lambda source: source.allocation_qty < 0)
        if not sources:
            return {}, {}
        service = self.env['ab_inventory_process'].sudo()
        posted = service._source_balances(self.audit_id.store_id.id, source_ids=sources.source_id.ids)
        available = service._source_balances(self.audit_id.store_id.id, source_ids=sources.source_id.ids,
                                            include_pending_outgoing=True)
        return posted, available

    def _stock_conflicts(self, balances=None):
        self.ensure_one()
        sources = self.sudo().source_ids.filtered(lambda source: source.allocation_qty < 0)
        posted, available = balances if balances is not None else self._allocation_balances()
        return [{'source': source.source_id.id, 'allocation': source.allocation_qty,
                 'posted': posted.get(source.source_id.id, 0),
                 'reserved': posted.get(source.source_id.id, 0) - available.get(source.source_id.id, 0),
                 'available': available.get(source.source_id.id, 0)} for source in sources
                if available.get(source.source_id.id, 0) + source.allocation_qty < 0]

    def _record_stock_conflict(self, conflicts):
        message = '\n'.join(_(
            'Source %(source)s: approved %(allocation)s; posted %(posted)s; reserved %(reserved)s; available %(available)s.',
            **conflict) for conflict in conflicts)
        self._edit({'allocation_unresolved': True, 'allocation_issue': message, 'allocation_resolution': False})
        self.audit_id._event(_('Allocation blocked'), _('Group %(group)s: %(message)s', group=self.id, message=message))

    def _validate_allocation(self):
        self.ensure_one()
        if sum(self.source_ids.mapped('allocation_qty')) != self.discrepancy:
            raise ValidationError(_('Source allocations must equal the accepted discrepancy.'))
        for source in self.source_ids:
            actual = source.source_id
            if actual and source.allocation_qty:
                normalized = (decimal(actual.price) / unit_factor(actual.product_id, actual.uom_id)).quantize(Decimal('0.001'))
                if actual.product_id != self.product_id or actual.exp_date != self.exp_date or actual.no_expiry != self.no_expiry or normalized != decimal(self.comparison_price):
                    raise ValidationError(_('Source grouping changed. Recount the affected group.'))
            if source.allocation_qty and source.allocation_qty * self.discrepancy <= 0:
                raise ValidationError(_('Allocation direction must match the discrepancy.'))
            if source.allocation_qty < -source.reference_qty:
                raise ValidationError(_('A shortage cannot exceed the source reference balance.'))
            if source.allocation_qty and not source.source_id and not source.new_source_approved:
                raise ValidationError(_('Approve the new surplus source before approval.'))


class AuditCount(models.Model):
    _name = 'ab_inventory_audit_count'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit Count Attempt'
    _order = 'id desc'

    line_id = fields.Many2one('ab_inventory_audit_line', required=True, index=True, ondelete='restrict')
    counter_id = fields.Many2one('res.users', required=True)
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    ended_at = fields.Datetime()
    input_method = fields.Selection([('manual', 'Manual'), ('barcode', 'Barcode'), ('excel', 'Excel')], required=True)
    state = fields.Selection([('active', 'Active'), ('valid', 'Valid'), ('invalid', 'Invalid'),
                              ('cancelled', 'Cancelled'), ('superseded', 'Superseded')], default='active', required=True)
    large_qty = fields.Float(digits=(16, 6))
    medium_qty = fields.Float(digits=(16, 6))
    small_qty = fields.Float(digits=(16, 6))
    quantity = fields.Float(digits=(24, 8), )
    reference_qty = fields.Float(digits=(24, 8), )
    boundary = fields.Json(groups=FINANCIAL)
    notes = fields.Text()
    reason = fields.Text()
    resolution_reason = fields.Text()
    revision = fields.Integer()
    export_token = fields.Char()
    import_digest = fields.Char()
    quantity_fingerprint = fields.Char()
    workbook_version = fields.Integer(default=2)
    _one_active = models.UniqueIndex('(line_id) WHERE state = \'active\'', 'Only one count may be active per group.')

    @api.depends('counter_id', 'started_at')
    def _compute_display_name(self):
        for count in self:
            count.display_name = _('Attempt %(number)s: %(counter)s', number=count.id, counter=count.counter_id.name)

    def _quantity_fingerprint(self, large, medium, small):
        values = [str(decimal(value).normalize()) for value in (large, medium, small)]
        return hashlib.sha256(json.dumps(values).encode()).hexdigest()

    def _confirm(self, large=0, medium=0, small=0, digest=None, ledger=None, notes=None):
        self.ensure_one()
        self.check_access('read')
        self.line_id.check_access('read')
        self.audit_id._authorize()
        if self.counter_id != self.env.user:
            raise AccessError(_('Only the counter who started this attempt can confirm it.'))
        quantity = count_quantity(self.line_id.product_id.sudo(), large, medium, small)
        fingerprint = self._quantity_fingerprint(large, medium, small)
        if self.state == 'valid' and self.quantity_fingerprint == fingerprint:
            return True
        self.line_id._authorize_count()
        if self.state != 'active':
            raise ValidationError(_('Confirmed quantities cannot change. Request a new count attempt.'))
        if self.revision != self.line_id.counting_revision:
            raise ValidationError(_('Group %s changed. Cancel the attempt with a reason, request a recount and export again.', self.line_id.id))
        if self.line_id.physical_absence and quantity:
            raise ValidationError(_('Use a stock observation for discovered stock instead of an absence count.'))
        boundary = self.sudo().boundary
        valid = boundary == self.line_id._boundary(ledger)
        reference = sum(item['balance'] for item in boundary['sources'].values())
        self._edit({'large_qty': large, 'medium_qty': medium, 'small_qty': small,
                    'quantity': quantity, 'reference_qty': reference, 'ended_at': fields.Datetime.now(),
                    'state': 'valid' if valid else 'invalid', 'import_digest': digest,
                    'quantity_fingerprint': fingerprint, 'notes': notes or False,
                    'reason': '' if valid else _('Stock movements or source membership changed during counting.')})
        line_values = {'state': 'counted' if valid else 'invalid'}
        if not valid:
            line_values['counting_revision'] = self.line_id.counting_revision + 1
        self.line_id._edit(line_values)
        self.audit_id._event(_('Count confirmed') if valid else _('Count invalidated'))
        return valid


class AuditSource(models.Model):
    _name = 'ab_inventory_audit_source'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit Source Allocation'
    _rec_name = 'source_id'

    line_id = fields.Many2one('ab_inventory_audit_line', required=True, index=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', ondelete='restrict')
    reference_qty = fields.Float(digits=(24, 8), )
    allocation_qty = fields.Float(digits=(24, 8), )
    allocation_reason = fields.Text()
    valuation_snapshot = fields.Json(groups=FINANCIAL)
    preview_cost = fields.Float(compute='_compute_preview', digits=(24, 10), groups=FINANCIAL)
    preview_value = fields.Float(compute='_compute_preview', digits=(16, 2), groups=FINANCIAL)
    frozen_cost = fields.Float(digits=(24, 10), groups=FINANCIAL)
    frozen_value = fields.Float(digits=(16, 2), groups=FINANCIAL)
    zero_cost_reason = fields.Text(groups=FINANCIAL)
    new_source_approved = fields.Boolean(groups=FINANCIAL)
    uom_id = fields.Many2one('ab_product_uom', groups=FINANCIAL)
    purchase_price = fields.Float(digits=(16, 3), groups=FINANCIAL)
    cost_supplied = fields.Boolean(groups=FINANCIAL)
    selling_price = fields.Float(digits=(16, 3), groups=FINANCIAL)
    discount = fields.Float(digits=(5, 3), groups=FINANCIAL)
    tax_ids = fields.Many2many('ab_taxes', groups=FINANCIAL)
    _source_unique = models.Constraint('UNIQUE(line_id, source_id)', 'This source is already allocated to this group.')

    def _compute_preview(self):
        for source in self:
            source.preview_cost = float(decimal(source._valuation()['small_cost'])) if source.source_id or source.cost_supplied else 0
            source.preview_value = source.preview_cost * source.allocation_qty

    def _lock_valuation(self):
        sources = self.source_id
        self.env['ab_inventory_process'].sudo()._lock_unit_definitions(
            sources.ids, product_ids=self.line_id.product_id.ids, uom_ids=self.uom_id.ids)
        sources.lock_for_update(allow_referencing=True)
        taxes = sources.taxes_ids | self.tax_ids
        taxes.sorted('id').lock_for_update(allow_referencing=True)
        sources.invalidate_recordset()
        taxes.invalidate_recordset()

    def _valuation(self):
        self.ensure_one()
        source = self.source_id
        if source:
            product, uom, price = source.product_id, source.uom_id, source.purchase_price
            discount, taxes = source.extra_discount_percentage, source.taxes_ids
            cost = decimal(source.unit_cost)
        else:
            if not self.cost_supplied:
                raise ValidationError(_('Supply the new source cost before approval.'))
            product, uom, price = self.line_id.product_id, self.uom_id, self.purchase_price
            discount, taxes = self.discount, self.tax_ids
            prototype = self.env['ab_product_source'].sudo().new({
                'product_id': product.id, 'uom_id': uom.id, 'purchase_price': price,
                'extra_discount_percentage': discount, 'taxes_ids': [fields.Command.set(taxes.ids)]})
            cost = decimal(prototype.unit_cost)
            if decimal(price) < 0 or not 0 <= decimal(discount) <= 100 or decimal(self.selling_price) < cost:
                raise ValidationError(_('The new source price must cover its nonnegative cost.'))
        factor = unit_factor(product, uom)
        return {'source': source.id, 'purchase_price': str(price), 'discount': str(discount),
                'selling_price': str(source.price if source else self.selling_price),
                'expiry': str(source.exp_date if source else self.line_id.exp_date),
                'no_expiry': source.no_expiry if source else self.line_id.no_expiry,
                'factor': str(factor), 'uom': uom.id, 'small_cost': str(cost / factor),
                'taxes': [[tax.id, str(tax.percentage), tax.apply_on_total] for tax in taxes.sorted('id')]}

    def _create_surplus_source(self):
        self.ensure_one()
        if not self.new_source_approved or self.allocation_qty <= 0:
            raise ValidationError(_('Only approved surplus sources can be created.'))
        source = self.env['ab_product_source'].sudo().with_context(workflow_context(self.env)).create({
                'product_id': self.line_id.product_id.id, 'uom_id': self.uom_id.id,
                'purchase_price': self.purchase_price, 'price': self.selling_price,
                'extra_discount_percentage': self.discount, 'taxes_ids': [fields.Command.set(self.tax_ids.ids)],
                'exp_date': self.line_id.exp_date, 'no_expiry': self.line_id.no_expiry,
                'audit_origin_id': self.audit_id.id, 'source_model': 'ab_inventory_audit'})
        if self._valuation()['small_cost'] != str(decimal(source.unit_cost) / unit_factor(source.product_id, source.uom_id)):
            raise ValidationError(_('The new source valuation differs from approval.'))
        self._edit({'source_id': source.id})
        return source


class AuditAdjustment(models.Model):
    _name = 'ab_inventory_audit_adjustment'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit Inventory Adjustment'
    _rec_name = 'source_id'

    audit_source_id = fields.Many2one('ab_inventory_audit_source', required=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', required=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_product_uom', required=True, ondelete='restrict')
    qty = fields.Float(digits=(24, 8), required=True)
    frozen_cost = fields.Float(digits=(24, 10), groups=FINANCIAL)
    value = fields.Float(digits=(16, 2), groups=FINANCIAL)
    balance_before = fields.Float(digits=(24, 8), )
    movement_id = fields.Many2one('ab_inventory', ondelete='restrict')
    _source_unique = models.Constraint('UNIQUE(audit_source_id)', 'This source adjustment has already been posted.')
