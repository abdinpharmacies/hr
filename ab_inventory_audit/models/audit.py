import hashlib
import json
from decimal import Decimal
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .common import FINANCIAL, WORKFLOW, decimal, money, unit_factor, workflow_context


class Audit(models.Model):
    _name = 'ab_inventory_audit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Inventory Audit'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda self: _('New Audit'))
    active = fields.Boolean(default=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True, index=True)
    scope = fields.Selection([('full', 'Full Branch'), ('partial', 'Selected Products')], required=True, default='partial')
    product_ids = fields.Many2many('ab_product', string='Selected Products')
    team_ids = fields.Many2many('res.users', string='Counters')
    manager_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    state = fields.Selection([('draft', 'Draft'), ('counting', 'Counting'), ('review', 'Review'),
                              ('approved', 'Approved'), ('posted', 'Posted'), ('cancelled', 'Cancelled')],
                             required=True, default='draft', readonly=True, index=True, copy=False)
    revision = fields.Integer(default=1, readonly=True, copy=False)
    approval_revision = fields.Integer(readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    posted_by = fields.Many2one('res.users', readonly=True, copy=False)
    posted_at = fields.Datetime(readonly=True, copy=False)
    opened_at = fields.Datetime(readonly=True, copy=False)
    correction_of_id = fields.Many2one('ab_inventory_audit', ondelete='restrict', copy=False)
    line_ids = fields.One2many('ab_inventory_audit_line', 'audit_id', readonly=True)
    coverage_ids = fields.One2many('ab_inventory_audit_coverage', 'audit_id', readonly=True)
    observation_ids = fields.One2many('ab_inventory_audit_observation', 'audit_id', readonly=True)
    count_ids = fields.One2many('ab_inventory_audit_count', 'audit_id', readonly=True)
    adjustment_ids = fields.One2many('ab_inventory_audit_adjustment', 'audit_id', readonly=True, groups=FINANCIAL)
    event_ids = fields.One2many('ab_inventory_audit_event', 'audit_id', readonly=True)
    config_id = fields.Many2one('ab_inventory_audit_config', readonly=True, groups=FINANCIAL)
    config_snapshot = fields.Json(readonly=True, groups=FINANCIAL)
    surplus_journal_id = fields.Many2one('ab_accounting_je_header', readonly=True, copy=False, groups=FINANCIAL)
    shortage_journal_id = fields.Many2one('ab_accounting_je_header', readonly=True, copy=False, groups=FINANCIAL)
    approval_digest = fields.Char(readonly=True, groups=FINANCIAL)
    surplus_value = fields.Float(compute='_compute_values', digits=(16, 2), groups=FINANCIAL)
    shortage_value = fields.Float(compute='_compute_values', digits=(16, 2), groups=FINANCIAL)
    progress = fields.Float(compute='_compute_progress')
    coverage_complete = fields.Boolean(compute='_compute_progress')
    movement_history = fields.Html(compute='_compute_movement_history')
    attachment_ids = fields.Many2many('ir.attachment', compute='_compute_attachments')

    def _compute_movement_history(self):
        report = self.env['report.ab_inventory_audit.results']
        for audit in self:
            if not audit.id:
                audit.movement_history = False
                continue
            title, columns, rows = report._sections(audit)[3]
            headings = Markup('').join(Markup('<th>%s</th>') % column for column in columns)
            body = Markup('').join(Markup('<tr>%s</tr>') % Markup('').join(
                Markup('<td>%s</td>') % value for value in row) for row in rows)
            audit.movement_history = Markup('<table class="table table-sm"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (headings, body)

    def _compute_attachments(self):
        for audit in self:
            if not audit.id:
                audit.attachment_ids = False
                continue
            audit.check_access('read')
            audit.attachment_ids = self.env['ir.attachment'].search([
                ('res_model', '=', self._name), ('res_id', '=', audit.id)])

    def _compute_values(self):
        for audit in self:
            sources = audit.line_ids.source_ids
            audit.surplus_value = sum(source.frozen_value if audit.state in ('approved', 'posted') else source.preview_value
                                      for source in sources if source.allocation_qty > 0)
            audit.shortage_value = -sum(source.frozen_value if audit.state in ('approved', 'posted') else source.preview_value
                                        for source in sources if source.allocation_qty < 0)

    @api.depends('line_ids.state', 'coverage_ids.state', 'observation_ids.state')
    def _compute_progress(self):
        for rec in self:
            coverage = rec.sudo().coverage_ids
            complete = len(coverage.filtered(lambda item: item.state == 'complete'))
            rec.progress = 100 * complete / len(coverage) if coverage else 0
            rec.coverage_complete = (bool(coverage) and complete == len(coverage)
                                     and not rec.sudo().observation_ids.filtered(lambda item: item.state == 'pending'))

    @api.model
    def _check_branch(self, store):
        store = store.exists()
        if not store or store.company_id not in self.env.companies:
            raise AccessError(_('Select a branch in an allowed company.'))
        if not self.env.user.has_group('base.group_system') and store not in self.env.user.inventory_store_ids:
            raise AccessError(_('This branch is not assigned to you.'))
        return store

    def _authorize(self, manager=False):
        self.ensure_one()
        self.check_access('read')
        self._check_branch(self.store_id)
        is_manager = self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_inventory_audit.group_manager')
        if manager and not is_manager:
            raise AccessError(_('An audit manager is required.'))
        if not manager and not is_manager and not self.env.user.has_group('ab_inventory_audit.group_counter'):
            raise AccessError(_('Counting permission is required.'))
        return is_manager

    def _lock(self, manager=False):
        self._authorize(manager)
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        self._check_branch(self.store_id)
        self.store_id.sudo()._lock_stock_scope()

    def _edit(self, vals):
        return self.sudo().with_context(workflow_context(self.env)).write(vals)

    def _event(self, action, reason=''):
        self.env['ab_inventory_audit_event']._new({
            'audit_id': self.id, 'actor_id': self.env.uid, 'action': action,
            'reason': reason, 'revision': self.revision})

    def _revise(self, reason):
        self._edit({'revision': self.revision + 1, 'approval_revision': 0,
                    'approved_by': False, 'approved_at': False, 'approval_digest': False})
        self._event(_('Revision'), reason)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_inventory_audit.group_manager')):
            raise AccessError(_('An audit manager is required.'))
        allowed = {'name', 'store_id', 'scope', 'product_ids', 'team_ids', 'manager_id', 'correction_of_id'}
        for vals in vals_list:
            if set(vals) - allowed:
                raise AccessError(_('Use the audit workflow actions.'))
            self._check_branch(self.env['ab_store'].browse(vals.get('store_id')))
        with self.env.cr.savepoint():
            records = super(Audit, self.with_context(workflow_context(self.env))).create(vals_list)
            for rec in records:
                rec._validate_team()
                if rec.name == _('New Audit'):
                    rec._edit({'name': 'AUD/%s/%06d' % (fields.Date.today().year, rec.id)})
                if rec.correction_of_id:
                    rec.correction_of_id.check_access('read')
                    if rec.correction_of_id.state != 'posted' or rec.correction_of_id.store_id != rec.store_id:
                        raise ValidationError(_('A corrective audit must reference a posted audit in the same branch.'))
                rec._event(_('Created'))
            return records.with_env(self.env)

    def write(self, vals):
        if self.env.context.get('_audit_workflow') is WORKFLOW:
            return super().write(vals)
        for rec in self:
            rec._authorize(True)
        if set(vals) == {'active'}:
            if any(rec.state not in ('posted', 'cancelled') for rec in self):
                raise ValidationError(_('Only posted or cancelled audits can be archived.'))
            return super().write(vals)
        allowed = {'name', 'store_id', 'scope', 'product_ids', 'team_ids', 'manager_id'}
        if set(vals) - allowed or any(rec.state != 'draft' for rec in self):
            raise AccessError(_('Use the audit workflow actions.'))
        with self.env.cr.savepoint():
            result = super().write(vals)
            for rec in self:
                rec._check_branch(rec.store_id)
                rec._validate_team()
            return result

    def unlink(self):
        raise AccessError(_('Cancel or archive audits instead of deleting them.'))

    def _validate_team(self):
        for user in self.team_ids | self.manager_id:
            if not user.active or user.share or self.company_id not in user.company_ids:
                raise ValidationError(_('Team members must be active internal users in this company.'))
            if not user.has_group('base.group_system') and self.store_id not in user.inventory_store_ids:
                raise ValidationError(_('Assign the branch to every team member first.'))
        if not (self.manager_id.has_group('base.group_system') or self.manager_id.has_group('ab_inventory_audit.group_manager')):
            raise ValidationError(_('Select an authorized audit manager.'))

    def _check_overlap(self, extra_products=()):
        others = self.sudo().with_context(active_test=False).search([
            ('id', '!=', self.id), ('store_id', '=', self.store_id.id),
            ('state', 'in', ['counting', 'review', 'approved'])])
        products = set(self.product_ids.ids) | set(self.sudo().coverage_ids.filtered(lambda item: item.decision != 'excluded').product_id.ids) | set(extra_products)
        for other in others:
            if self.scope == 'full' or other.scope == 'full' or products.intersection(set(other.product_ids.ids) | set(other.coverage_ids.filtered(lambda item: item.decision != 'excluded').product_id.ids)):
                raise ValidationError(_('An active audit already covers this branch and product scope.'))

    def _ledger(self, product_ids=None, group_keys=None, include_moves=True):
        domain = [('store_id', '=', self.store_id.id)]
        if product_ids is not None:
            domain.append(('product_id', 'in', product_ids))
        elif self.scope == 'partial':
            domain.append(('product_id', 'in', list(set(self.product_ids.ids) | set(
                self.sudo().coverage_ids.filtered(lambda item: item.decision == 'included').product_id.ids))))
        inventory = self.env['ab_inventory'].sudo()
        source_groups = inventory._read_group(domain, ['source_id'], [])
        sources = self.env['ab_product_source'].sudo().browse([source.id for source, in source_groups if source])
        result = {}
        for source in sources:
            factor = unit_factor(source.product_id, source.uom_id)
            price = (decimal(source.price) / factor).quantize(Decimal('0.001'))
            key = json.dumps([source.product_id.id, str(source.exp_date or ''), source.no_expiry, str(price)])
            if group_keys is not None and key not in group_keys:
                continue
            result.setdefault(key, {'product_id': source.product_id.id, 'exp_date': source.exp_date,
                                    'no_expiry': source.no_expiry, 'price': float(price), 'sources': {}, 'moves': []})
            result[key]['sources'][source.id] = {'factor': str(factor), 'uom': source.uom_id.id}
        source_keys = {source_id: key for key, data in result.items() for source_id in data['sources']}
        service = self.env['ab_inventory_process'].sudo()
        posted = service._source_balances(self.store_id.id, source_ids=list(source_keys))
        available = service._source_balances(self.store_id.id, source_ids=list(source_keys), include_pending_outgoing=True)
        for source_id, key in source_keys.items():
            result[key]['sources'][source_id].update({
                'balance': posted.get(source_id, 0),
                'reserved': posted.get(source_id, 0) - available.get(source_id, 0)})
        if include_moves and source_keys:
            movements = inventory.search_read(domain + [('source_id', 'in', list(source_keys)), ('status', '=', 'saved')],
                                               ['id', 'source_id', 'qty'], order='id', load='')
            for movement in movements:
                result[source_keys[movement['source_id']]]['moves'].append([movement['id'], movement['qty']])
        return result

    def _refresh_coverage(self):
        ledger = self._ledger(include_moves=False)
        products = set(data['product_id'] for data in ledger.values())
        if self.state == 'draft':
            products.update(self.product_ids.ids)
        missing = products - set(self.sudo().coverage_ids.product_id.ids)
        if missing:
            self._check_overlap(missing)
            self.env['ab_inventory_audit_coverage']._new([
                {'audit_id': self.id, 'product_id': product,
                 'origin': 'opening' if self.state == 'draft' else 'additional'}
                for product in sorted(missing)])
        existing = {line.group_key: line for line in self.sudo().line_ids}
        new_values = []
        source_values = []
        for key, data in ledger.items():
            if key in existing:
                line = existing[key]
                if line.accepted_count_id:
                    missing_sources = set(data['sources']) - set(line.source_ids.source_id.ids)
                    source_values.extend({'audit_id': self.id, 'line_id': line.id, 'source_id': source_id}
                                         for source_id in sorted(missing_sources))
                continue
            new_values.append({'audit_id': self.id, 'group_key': key,
                               'product_id': data['product_id'], 'exp_date': data['exp_date'],
                               'no_expiry': data['no_expiry'], 'comparison_price': data['price'],
                               'state': 'new' if self.state != 'draft' else 'uncounted',
                               'assigned_ids': [fields.Command.set(self.team_ids.ids)]})
        if source_values:
            self.env['ab_inventory_audit_source']._new(source_values)
        if new_values:
            self.env['ab_inventory_audit_line']._new(new_values)
            if self.state != 'draft':
                self._revise(_('New groups require a coverage decision.'))
                if self.state == 'approved':
                    self._edit({'state': 'review'})
        return ledger

    def action_prepare(self):
        with self.env.cr.savepoint():
            self._lock(True)
            if self.state != 'draft':
                raise ValidationError(_('Only draft audits can be prepared.'))
            self._validate_team()
            if self.scope == 'partial' and not self.product_ids:
                raise ValidationError(_('Select products for the partial audit.'))
            self._check_overlap()
            self._refresh_coverage()
            self._edit({'state': 'counting', 'opened_at': fields.Datetime.now()})
            self._event(_('Counting opened'))
        return True

    def action_refresh(self):
        with self.env.cr.savepoint():
            self._lock(True)
            if self.state not in ('counting', 'review', 'approved'):
                raise ValidationError(_('Coverage can only change in an active audit.'))
            self._refresh_coverage()
        return True

    def action_review(self):
        with self.env.cr.savepoint():
            self._lock(True)
            if self.state != 'counting':
                raise ValidationError(_('Only a counting audit can enter review.'))
            self._refresh_coverage()
            self._edit({'state': 'review'})
            self._event(_('Review opened'))
        return True

    def _approval_data(self):
        return {'revision': self.revision, 'config': self.sudo().config_id._snapshot(),
                'sources': [source._valuation() | {'id': source.id, 'allocation': source.allocation_qty}
                            for source in self.sudo().line_ids.source_ids.sorted('id') if source.allocation_qty]}

    def _digest(self):
        return hashlib.sha256(json.dumps(self._approval_data(), sort_keys=True).encode()).hexdigest()

    def action_approve(self):
        with self.env.cr.savepoint():
            self._lock(True)
            if self.state != 'review':
                raise ValidationError(_('Only a reviewed audit can be approved.'))
            self._refresh_coverage()
            lines = self.sudo().line_ids
            if (not self.sudo().coverage_ids or self.sudo().coverage_ids.filtered(lambda item: item.state == 'unresolved')
                    or self.sudo().observation_ids.filtered(lambda item: item.state == 'pending')):
                raise ValidationError(_('Resolve every product coverage and stock observation before approval.'))
            if not lines or any(line.state not in ('accepted', 'excluded') for line in lines):
                raise ValidationError(_('Resolve every count and coverage decision before approval.'))
            accepted = lines.filtered(lambda line: line.state == 'accepted')
            if self.env.uid in accepted.accepted_count_id.counter_id.ids:
                raise AccessError(_('A manager who performed an accepted count cannot approve this audit.'))
            if self.sudo().count_ids.filtered(lambda count: count.state in ('active', 'invalid')):
                raise ValidationError(_('Resolve active count attempts before approval.'))
            today = fields.Date.context_today(self)
            configs = self.env['ab_inventory_audit_config'].search([
                ('store_id', '=', self.store_id.id), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today)], order='date_from desc, id desc')
            if not configs:
                raise ValidationError(_('Configure audit accounting for this branch and date.'))
            config = configs[0]
            config.lock_for_update(allow_referencing=True)
            config._validate_posting()
            balances = accepted._allocation_balances()
            for line in accepted:
                if line.allocation_unresolved:
                    raise ValidationError(_('Resolve the blocked allocation for group %s with a documented decision.', line.id))
                line._validate_allocation()
                if line._stock_conflicts(balances):
                    raise ValidationError(_('Current stock prevents the allocation for group %s. Review the source quantities.', line.id))
            sources = accepted.source_ids.filtered('allocation_qty')
            sources._lock_valuation()
            for source in sources:
                snapshot = source._valuation()
                cost = decimal(snapshot['small_cost'])
                if cost < 0 or (not cost and not source.zero_cost_reason):
                    raise ValidationError(_('Zero cost requires an acknowledgement reason; negative cost is forbidden.'))
                source._edit({'valuation_snapshot': snapshot, 'frozen_cost': float(cost),
                              'frozen_value': float(money(cost * source.allocation_qty))})
            self._edit({'config_id': config.id, 'config_snapshot': config._snapshot(),
                        'approved_by': self.env.uid, 'approved_at': fields.Datetime.now(),
                        'approval_revision': self.revision, 'state': 'approved'})
            self._edit({'approval_digest': self._digest()})
            self._event(_('Approved'))
        return True

    def action_post(self, revision=None):
        with self.env.cr.savepoint():
            self._lock(True)
            if revision is not None and revision != self.approval_revision:
                raise ValidationError(_('The approval revision is stale.'))
            if self.state == 'posted':
                return True
            if self.state != 'approved' or self.approval_revision != self.revision:
                raise ValidationError(_('Approve the current revision before posting.'))
            if self.env.uid in self.sudo().line_ids.accepted_count_id.counter_id.ids:
                raise AccessError(_('A manager who performed an accepted count cannot post this audit.'))
            self._refresh_coverage()
            if self.state != 'approved':
                return False
            config = self.config_id
            config.lock_for_update(allow_referencing=True)
            config._validate_posting()
            sources = self.sudo().line_ids.source_ids.filtered('allocation_qty')
            sources._lock_valuation()
            if self.approval_digest != self._digest():
                self._edit({'state': 'review'})
                self._revise(_('Valuation or accounting inputs changed. Reapprove the audit.'))
                return False
            for line in self.sudo().line_ids.filtered(lambda line: line.state == 'accepted'):
                line._validate_allocation()
            blocked = False
            accepted = self.sudo().line_ids.filtered(lambda item: item.state == 'accepted').with_env(self.env)
            balances = accepted._allocation_balances()
            for line in accepted:
                conflicts = line._stock_conflicts(balances)
                if conflicts:
                    line._record_stock_conflict(conflicts)
                    blocked = True
            if blocked:
                self._edit({'state': 'review'})
                self._revise(_('Current stock or reservations prevent the approved shortage. Resolve the blocked allocations.'))
                return False
            posted = self.env['ab_inventory_process'].sudo()._source_balances(
                self.store_id.id, source_ids=sources.source_id.ids)
            totals = {'surplus': Decimal(0), 'shortage': Decimal(0)}
            for source in sources:
                actual_source = source.source_id or source._create_surplus_source()
                adjustment = self.env['ab_inventory_audit_adjustment']._new({
                    'audit_id': self.id, 'audit_source_id': source.id, 'source_id': actual_source.id,
                    'uom_id': actual_source.product_id._stock_reference_unit().id, 'qty': source.allocation_qty,
                    'frozen_cost': source.frozen_cost, 'value': source.frozen_value,
                    'balance_before': posted.get(actual_source.id, 0)})
                movement = self.env['ab_inventory_process'].sudo().inventory_write(
                    adjustment.sudo(), abs(adjustment.qty), self.store_id.id, sign=1 if adjustment.qty > 0 else -1)
                adjustment._edit({'movement_id': movement.id})
                direction = 'surplus' if source.allocation_qty > 0 else 'shortage'
                totals[direction] += abs(decimal(source.frozen_value))
            for direction, amount in totals.items():
                if not amount:
                    continue
                inventory = config.inventory_account_id.id
                opposite = config.surplus_account_id.id if direction == 'surplus' else config.shortage_account_id.id
                debit, credit = (inventory, opposite) if direction == 'surplus' else (opposite, inventory)
                common = {'store_id': self.store_id.id, 'costcenter_id': config.costcenter_id.id,
                          'due_date': str(fields.Date.context_today(self)), 'explain': self.name}
                journal = self.env['ab_accounting_je_header'].with_context(workflow_context(self.env)).post_journal({
                    'account_id': inventory, 'store_id': self.store_id.id,
                    'costcenter_id': config.costcenter_id.id, 'doctype_id': config.doctype_id.id,
                    'res_header_ref': self._name, 'res_header_id': self.id,
                    'lines': [dict(common, account_id=debit, debit_val=float(amount)),
                              dict(common, account_id=credit, credit_val=float(amount))]})
                self._edit({direction + '_journal_id': journal.id})
            self._edit({'state': 'posted', 'posted_at': fields.Datetime.now(), 'posted_by': self.env.uid})
            self._event(_('Posted'))
        return True

    def action_fast_count(self):
        self._authorize()
        return {'type': 'ir.actions.client', 'tag': 'ab_inventory_audit.fast_count',
                'context': {'active_id': self.id, 'active_model': self._name},
                'params': {'audit_id': self.id}}

    def action_workflow(self):
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_inventory_audit_wizard',
                'view_mode': 'form', 'views': [(False, 'form')], 'name': _('Audit Workflow'), 'target': 'new', 'context': {'default_audit_id': self.id}}

    def action_post_wizard(self):
        self._authorize(True)
        action = self.action_workflow()
        action['context']['default_operation'] = 'post'
        return action

    def action_count_sheet(self):
        self._authorize()
        return self.env['ab_inventory_audit_wizard']._export(self)
