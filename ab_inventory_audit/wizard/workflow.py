import base64
import hashlib
import io
import json
import uuid
import zipfile

import openpyxl
import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from ..models.common import FINANCIAL, count_quantity, decimal, unit_factor


COLUMNS = ['audit_id', 'group_id', 'attempt_id', 'revision', 'token', 'product_code',
           'product', 'expiry', 'comparison_price', 'posted_qty', 'reserved_qty',
           'large_qty', 'medium_qty', 'small_qty', 'format_version', 'large_unit', 'medium_unit', 'small_unit', 'available_qty']


class AuditWizard(models.TransientModel):
    _name = 'ab_inventory_audit_wizard'
    _description = 'Audit Workflow'

    audit_id = fields.Many2one('ab_inventory_audit', required=True, ondelete='cascade')
    store_id = fields.Many2one(related='audit_id.store_id', store=True)
    company_id = fields.Many2one(related='audit_id.company_id', store=True)
    surplus_value = fields.Float(related='audit_id.surplus_value', groups=FINANCIAL)
    shortage_value = fields.Float(related='audit_id.shortage_value', groups=FINANCIAL)
    line_id = fields.Many2one('ab_inventory_audit_line')
    group_ids = fields.Many2many('ab_inventory_audit_line', string='Selected Count Groups')
    count_id = fields.Many2one('ab_inventory_audit_count')
    operation = fields.Selection([
        ('absence', 'Start Physical Absence Count'), ('include_observation', 'Include Stock Observation'),
        ('exclude_observation', 'Exclude Stock Observation'),
        ('count', 'Confirm Count'), ('cancel_attempt', 'Cancel Attempt'), ('review', 'Accept Count'),
        ('recount', 'Request Recount'), ('assign', 'Assign Counters'), ('include', 'Include New Coverage'),
        ('exclude', 'Exclude New Coverage'), ('reopen', 'Reopen Approval'), ('cancel', 'Cancel Audit'),
        ('resolve_allocation', 'Resolve Blocked Allocation'),
        ('allocate', 'Override Allocation'), ('unidentified', 'Unidentified Physical Stock'),
        ('source', 'Approve Surplus Source'), ('products', 'Select Products by Category'),
        ('export', 'Export Selected Groups'), ('import', 'Import Count Sheet'),
        ('download', 'Download Count Sheet'), ('post', 'Post Approved Audit')],
        required=True, default='count')
    observation_id = fields.Many2one('ab_inventory_audit_observation')
    count_notes = fields.Text()
    large_unit_id = fields.Many2one(related='line_id.large_unit_id')
    medium_unit_id = fields.Many2one(related='line_id.medium_unit_id')
    small_unit_id = fields.Many2one(related='line_id.small_unit_id')
    attachment_ids = fields.Many2many(related='audit_id.attachment_ids')
    observed_qty = fields.Float(digits=(16, 6))
    reason = fields.Text()
    large_qty = fields.Float(digits=(16, 6))
    medium_qty = fields.Float(digits=(16, 6))
    small_qty = fields.Float(digits=(16, 6))
    counter_ids = fields.Many2many('res.users')
    product_id = fields.Many2one('ab_product')
    category_id = fields.Many2one('ab_product_group')
    source_id = fields.Many2one('ab_product_source', groups=FINANCIAL)
    audit_source_id = fields.Many2one('ab_inventory_audit_source', groups=FINANCIAL)
    allocation_qty = fields.Float(digits=(24, 8), )
    exp_date = fields.Date()
    no_expiry = fields.Boolean()
    uom_id = fields.Many2one('ab_product_uom')
    purchase_price = fields.Float(digits=(16, 3), groups=FINANCIAL)
    cost_supplied = fields.Boolean(groups=FINANCIAL)
    selling_price = fields.Float(digits=(16, 3))
    discount = fields.Float(digits=(5, 3), groups=FINANCIAL)
    tax_ids = fields.Many2many('ab_taxes', groups=FINANCIAL)
    zero_cost_reason = fields.Text(groups=FINANCIAL)
    file = fields.Binary(attachment=False)
    filename = fields.Char()
    preview = fields.Text(readonly=True)
    preview_digest = fields.Char(readonly=True)

    def _scope(self):
        self.ensure_one()
        self.check_access('write')
        self.audit_id.check_access('read')
        self.audit_id._check_branch(self.audit_id.store_id)
        if self.line_id and self.line_id.audit_id != self.audit_id:
            raise AccessError(_('The group belongs to another audit.'))
        if self.count_id and (self.count_id.audit_id != self.audit_id or self.count_id.line_id != self.line_id):
            raise AccessError(_('The attempt belongs to another group.'))
        if self.observation_id:
            self.observation_id.check_access('read')
            if self.observation_id.audit_id != self.audit_id:
                raise AccessError(_('The observation belongs to another audit.'))
        if self.line_id:
            self.line_id.check_access('read')
        if self.count_id:
            self.count_id.check_access('read')

    def action_apply(self):
        self._scope()
        with self.env.cr.savepoint():
            audit = self.audit_id
            manager = self.operation not in ('count', 'cancel_attempt', 'import', 'export', 'download', 'unidentified', 'absence')
            audit._lock(manager)
            if self.operation == 'absence':
                return self._absence()
            if self.operation in ('include_observation', 'exclude_observation'):
                self._decide_observation()
                return {'type': 'ir.actions.act_window_close'}
            if self.operation == 'export':
                if not self.group_ids:
                    raise ValidationError(_('Select count groups to export.'))
                return self._export(audit, self.group_ids)
            if self.operation == 'post':
                if not audit.action_post(audit.approval_revision):
                    return {'type': 'ir.actions.act_window', 'res_model': audit._name, 'res_id': audit.id,
                            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current'}
                return {'type': 'ir.actions.act_window_close'}
            if self.operation in ('download', 'import'):
                return self.action_import() if self.operation == 'import' else True
            if self.operation == 'count':
                if not self.count_id:
                    raise ValidationError(_('Select the active count attempt.'))
                self.count_id._confirm(self.large_qty, self.medium_qty, self.small_qty, notes=self.count_notes)
            elif self.operation == 'cancel_attempt':
                self.line_id._authorize_count()
                if self.count_id.counter_id != self.env.user or self.count_id.state != 'active' or not self.reason:
                    raise ValidationError(_('Only the counter may cancel an active attempt, with a reason.'))
                self.count_id._edit({'state': 'cancelled', 'reason': self.reason, 'ended_at': fields.Datetime.now()})
                self.line_id._edit({'state': 'uncounted'})
                audit._event(_('Attempt cancelled'), self.reason)
            elif self.operation == 'unidentified':
                self._unidentified()
            elif self.operation == 'products':
                if audit.state != 'draft' or not self.category_id:
                    raise ValidationError(_('Select a category on a draft audit.'))
                products = self.env['ab_product'].search([('groups_ids', 'in', self.category_id.ids)])
                audit.write({'product_ids': [fields.Command.link(product.id) for product in products]})
            else:
                if audit.state not in ('counting', 'review', 'approved') and not (audit.state == 'draft' and self.operation == 'cancel'):
                    raise ValidationError(_('This audit is not open for review.'))
                if audit.state == 'approved' and self.operation not in ('reopen', 'cancel'):
                    raise ValidationError(_('Reopen the approval before changing reviewed data.'))
                if self.operation in ('recount', 'exclude', 'reopen', 'cancel', 'allocate', 'source', 'resolve_allocation') and not self.reason:
                    raise ValidationError(_('A reason is required.'))
                line = self.line_id
                if self.operation in ('review', 'recount', 'include', 'exclude', 'assign', 'allocate', 'source', 'resolve_allocation') and not line:
                    raise ValidationError(_('Select a count group.'))
                if self.operation == 'review':
                    line._accept(self.count_id, self.reason)
                elif self.operation == 'recount':
                    for count in line.sudo().count_ids.filtered(lambda item: item.state in ('active', 'valid', 'invalid')):
                        count._edit({'state': 'superseded', 'resolution_reason': self.reason})
                    line._edit({'state': 'uncounted', 'accepted_count_id': False, 'discrepancy': 0,
                                'counted_qty': 0, 'reference_qty': 0})
                    line.sudo().source_ids._edit({'allocation_qty': 0})
                    audit._revise(self.reason)
                elif self.operation == 'assign':
                    if not self.counter_ids or self.counter_ids - audit.team_ids:
                        raise ValidationError(_('Select counters from this audit team.'))
                    if line.sudo().count_ids.filtered(lambda item: item.state == 'active'):
                        raise ValidationError(_('Cancel active attempts before changing assignments.'))
                    line._edit({'assigned_ids': [fields.Command.set(self.counter_ids.ids)]})
                    audit._revise(_('Count assignments changed'))
                elif self.operation in ('include', 'exclude'):
                    if line.state != 'new':
                        raise ValidationError(_('Only newly discovered coverage may be included or excluded.'))
                    audit._check_overlap(line.product_id.ids)
                    line._edit({'state': 'uncounted' if self.operation == 'include' else 'excluded',
                                'exclusion_reason': self.reason if self.operation == 'exclude' else False})
                    coverage = audit.sudo().coverage_ids.filtered(lambda item: item.product_id == line.product_id)
                    product_lines = audit.sudo().line_ids.filtered(lambda item: item.product_id == line.product_id)
                    coverage._edit({'decision_reason': self.reason or _('Coverage included'),
                                    'decision': 'excluded' if all(item.state == 'excluded' for item in product_lines) else 'included'})
                    audit._revise(self.reason or _('Coverage included'))
                elif self.operation == 'reopen':
                    audit._edit({'state': 'review'})
                    audit._revise(self.reason)
                elif self.operation == 'cancel':
                    audit._edit({'state': 'cancelled'})
                    audit._revise(self.reason)
                elif self.operation == 'resolve_allocation':
                    if not line.allocation_unresolved or line.state != 'accepted':
                        raise ValidationError(_('Select an accepted group with a blocked allocation.'))
                    line._validate_allocation()
                    if line._stock_conflicts():
                        raise ValidationError(_('Stock or reservations still prevent this allocation.'))
                    line._edit({'allocation_unresolved': False, 'allocation_resolution': self.reason})
                    audit._revise(self.reason)
                elif self.operation == 'allocate':
                    source = self.audit_source_id
                    if source.line_id != line:
                        raise AccessError(_('Select a source from this count group.'))
                    if self.allocation_qty < -source.reference_qty:
                        raise ValidationError(_('A shortage cannot exceed the source reference balance.'))
                    source._edit({'allocation_qty': self.allocation_qty, 'allocation_reason': self.reason,
                                  'zero_cost_reason': self.zero_cost_reason})
                    audit._revise(self.reason)
                elif self.operation == 'source':
                    self._surplus_source()
                audit._event(dict(self._fields['operation']._description_selection(self.env))[self.operation], self.reason)
        return {'type': 'ir.actions.act_window_close'}

    def _unidentified(self):
        audit = self.audit_id
        audit._authorize()
        if audit.state not in ('counting', 'review') or not self.product_id or not self.reason:
            raise ValidationError(_('Select a product and document the unidentified stock.'))
        self.product_id.check_access('read')
        if not self.no_expiry and not self.exp_date:
            raise ValidationError(_('Specify expiry or explicitly select no expiry.'))
        if self.no_expiry and self.exp_date:
            raise ValidationError(_('No-expiry stock cannot have an expiry date.'))
        factor = unit_factor(self.product_id.sudo(), self.uom_id)
        price = (decimal(self.selling_price) / factor).quantize(decimal('0.001'))
        if price < 0:
            raise ValidationError(_('Selling price must be nonnegative.'))
        if self.env.user not in audit.team_ids and not audit._authorize():
            raise AccessError(_('Only assigned team members may record stock observations.'))
        quantity = decimal(self.observed_qty)
        if quantity <= 0 or quantity * factor != (quantity * factor).to_integral_value():
            raise ValidationError(_('Record a positive quantity in the reference unit.'))
        self.env['ab_inventory_audit_observation']._new({
            'audit_id': audit.id, 'product_id': self.product_id.id, 'counter_id': self.env.uid,
            'quantity': self.observed_qty, 'uom_id': self.uom_id.id, 'exp_date': self.exp_date,
            'no_expiry': self.no_expiry, 'selling_price': self.selling_price, 'notes': self.reason})
        audit._revise(self.reason)
        audit._event(_('Unidentified stock recorded'), self.reason)

    def _absence(self):
        audit = self.audit_id
        manager = audit._authorize()
        coverage = audit.sudo().coverage_ids.filtered(
            lambda item: item.product_id == self.product_id and item.decision == 'included')
        if audit.state not in ('counting', 'review') or not coverage:
            raise ValidationError(_('Select an included product for physical absence confirmation.'))
        if not manager and self.env.user not in audit.team_ids:
            raise AccessError(_('Only assigned team members may confirm physical absence.'))
        if audit.sudo().line_ids.filtered(lambda line: line.product_id == self.product_id):
            raise ValidationError(_('Count the existing product groups, using explicit zero for empty stock.'))
        line = self.env['ab_inventory_audit_line']._new({
            'audit_id': audit.id, 'product_id': self.product_id.id,
            'group_key': 'absence:%s' % self.product_id.id, 'physical_absence': True,
            'assigned_ids': [fields.Command.set(audit.team_ids.ids)]})
        return line.action_start()

    def _decide_observation(self):
        audit = self.audit_id
        audit._authorize(True)
        observation = self.observation_id
        if audit.state not in ('counting', 'review') or not observation or observation.state != 'pending' or not self.reason:
            raise ValidationError(_('Select a pending stock observation and document the decision.'))
        included = self.operation == 'include_observation'
        coverage = audit.sudo().coverage_ids.filtered(lambda item: item.product_id == observation.product_id)
        line = self.env['ab_inventory_audit_line']
        if included:
            audit._check_overlap(observation.product_id.ids)
            if not self.uom_id or (not self.no_expiry and not self.exp_date) or (self.no_expiry and self.exp_date):
                raise ValidationError(_('Approve the unit and expiry details before counting discovered stock.'))
            factor = unit_factor(observation.product_id.sudo(), self.uom_id)
            price = (decimal(self.selling_price) / factor).quantize(decimal('0.001'))
            if price < 0:
                raise ValidationError(_('Selling price must be nonnegative.'))
            key = json.dumps([observation.product_id.id, str(self.exp_date or ''), self.no_expiry, str(price)])
            line = audit.sudo().line_ids.filtered(lambda item: item.group_key == key).with_env(self.env)
            if line and line.state != 'uncounted':
                raise ValidationError(_('Request a recount of the existing group before including discovered stock.'))
            if not line:
                line = self.env['ab_inventory_audit_line']._new({
                    'audit_id': audit.id, 'product_id': observation.product_id.id, 'group_key': key,
                    'exp_date': self.exp_date, 'no_expiry': self.no_expiry, 'comparison_price': float(price),
                    'assigned_ids': [fields.Command.set(audit.team_ids.ids)]})
            absence = audit.sudo().line_ids.filtered(lambda item: item.product_id == observation.product_id and item.physical_absence)
            if absence:
                absence.count_ids.filtered(lambda item: item.state in ('active', 'valid', 'invalid'))._edit(
                    {'state': 'superseded', 'resolution_reason': self.reason})
                absence._edit({'state': 'excluded', 'exclusion_reason': self.reason})
        if not coverage:
            self.env['ab_inventory_audit_coverage']._new({
                'audit_id': audit.id, 'product_id': observation.product_id.id, 'origin': 'additional',
                'decision': 'included' if included else 'excluded', 'decision_reason': self.reason})
        elif included:
            coverage._edit({'decision': 'included', 'decision_reason': self.reason})
        if included:
            line._edit({'counting_revision': line.counting_revision + 1})
        observation._edit({'state': 'included' if included else 'excluded', 'decision_reason': self.reason,
                           'decided_by': self.env.uid, 'decided_at': fields.Datetime.now(), 'line_id': line.id})
        audit._revise(self.reason)
        audit._event(_('Stock observation reviewed'), self.reason)

    def _surplus_source(self):
        line = self.line_id
        if line.discrepancy <= 0 or line.state != 'accepted':
            raise ValidationError(_('Accept a surplus count before selecting its source.'))
        vals = {'audit_id': self.audit_id.id, 'line_id': line.id, 'allocation_qty': self.allocation_qty,
                'allocation_reason': self.reason, 'zero_cost_reason': self.zero_cost_reason}
        if self.source_id:
            self.source_id.check_access('read')
            source = self.source_id.sudo()
            if source.product_id != line.product_id or source.no_expiry != line.no_expiry or source.exp_date != line.exp_date:
                raise ValidationError(_('The selected source must match product and expiry.'))
            if (source.integration_store_id and source.integration_store_id != self.audit_id.store_id) or (source.audit_origin_id and source.audit_origin_id.store_id != self.audit_id.store_id):
                raise AccessError(_('The selected source belongs to another branch.'))
            normalized = (decimal(source.price) / unit_factor(source.product_id, source.uom_id)).quantize(decimal('0.001'))
            if normalized != decimal(line.comparison_price):
                raise ValidationError(_('The selected source must match the comparison price.'))
            vals['source_id'] = source.id
        else:
            if not self.cost_supplied:
                raise ValidationError(_('Acknowledge that the new source cost was supplied.'))
            factor = unit_factor(line.product_id.sudo(), self.uom_id)
            if (decimal(self.selling_price) / factor).quantize(decimal('0.001')) != decimal(line.comparison_price):
                raise ValidationError(_('The new source must match the comparison price.'))
            vals.update({'new_source_approved': True, 'uom_id': self.uom_id.id,
                         'purchase_price': self.purchase_price, 'cost_supplied': True,
                         'selling_price': self.selling_price, 'discount': self.discount,
                         'tax_ids': [fields.Command.set(self.tax_ids.ids)]})
        existing = line.sudo().source_ids.filtered(lambda item: self.source_id and item.source_id == self.source_id)
        if existing:
            existing._edit({key: value for key, value in vals.items() if key not in ('audit_id', 'line_id')})
        else:
            self.env['ab_inventory_audit_source']._new(vals)
        self.audit_id._revise(self.reason)

    @api.model
    def _export(self, audit, selected=None):
        with self.env.cr.savepoint():
            audit._lock()
            lines = self.env['ab_inventory_audit_line'].search([
                ('audit_id', '=', audit.id), ('state', 'in', ['uncounted', 'invalid', 'counted'])])
            if selected is not None:
                selected.check_access('read')
                if selected - lines:
                    raise ValidationError(_('Select available count groups from this audit.'))
                lines = selected
            if not lines:
                raise ValidationError(_('No assigned groups are available for export.'))
            token = str(uuid.uuid4())
            ledger = audit._ledger(product_ids=lines.product_id.ids,
                                   group_keys=None if any(lines.mapped('physical_absence')) else set(lines.mapped('group_key')))
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
            for line in lines:
                line._authorize_count()
            attempts = self.env['ab_inventory_audit_count']._new([
                {'audit_id': audit.id, 'line_id': line.id, 'counter_id': self.env.uid,
                 'input_method': 'excel', 'boundary': line._boundary(ledger),
                 'export_token': token, 'revision': line.counting_revision} for line in lines])
            lines._edit({'state': 'counting'})
            audit._event(_('Count sheet exported'), str(len(lines)))
            sheet = workbook.add_worksheet('Count')
            sheet.write_row(0, 0, COLUMNS)
            sheet.set_row(0, None, None, {'hidden': True})
            sheet.write_row(1, 0, [_('Audit'), _('Count Groups'), _('Count Attempts'), _('Revision'),
                                   _('Export Token'), _('Code'), _('Product'), _('Expiry'),
                                   _('Comparison Price'), _('Posted Qty'), _('Reserved Qty'),
                                   _('Large Qty'), _('Medium Qty'), _('Small Qty'), _('Workbook Format'), _('Unit L'), _('Unit M'), _('Unit S'), _('Available Qty')])
            for row, (line, attempt) in enumerate(zip(lines, attempts), 2):
                data = ledger.get(line.group_key, {}).get('sources', {})
                sheet.write_row(row, 0, [audit.id, line.id, attempt.id, line.counting_revision, token,
                                        line.product_code or '', line.product_id.display_name,
                                        str(line.exp_date or ''), line.comparison_price,
                                        sum(item['balance'] for item in data.values()),
                                        sum(item['reserved'] for item in data.values()),
                                        None, None, None, 2, line.large_unit_id.display_name,
                                        line.medium_unit_id.display_name, line.small_unit_id.display_name,
                                        sum(item['balance'] - item['reserved'] for item in data.values())])
            sheet.freeze_panes(2, 7)
            sheet.set_column(0, 4, 12, None, {'hidden': True})
            sheet.set_column(5, 13, 20)
            sheet.set_column(14, 14, 12, None, {'hidden': True})
            sheet.set_column(15, 18, 20)
            workbook.close()
            wizard = self.create({'audit_id': audit.id, 'operation': 'download',
                                  'file': base64.b64encode(output.getvalue()), 'filename': 'audit-count.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': wizard.id,
                'view_mode': 'form', 'views': [(False, 'form')], 'name': _('Audit Workflow'), 'target': 'new'}

    def _load_rows(self):
        self._scope()
        if not self.file:
            raise ValidationError(_('Upload an exported count workbook.'))
        try:
            data = base64.b64decode(self.file, validate=True)
            if len(data) > 5 * 1024 * 1024:
                raise ValueError()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 40 * 1024 * 1024:
                    raise ValueError()
            workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False)
            if workbook.sheetnames != ['Count']:
                raise ValueError()
            sheet = workbook['Count']
            if sheet.max_row > 50002 or sheet.max_column != len(COLUMNS):
                raise ValueError()
            rows = list(sheet.iter_rows(values_only=True))
            workbook.close()
            if list(rows[0]) != COLUMNS:
                raise ValueError()
        except Exception:
            raise ValidationError(_('Use workbook format version 2 within the size limit. Older workbooks are incompatible; cancel their attempts with a reason and export again.')) from None
        digest = hashlib.sha256(data).hexdigest()
        checked, errors, seen = [], [], set()
        attempt_ids = {values[2] for values in rows[2:] if len(values) > 2 and type(values[2]) is int}
        attempts = {attempt.id: attempt for attempt in self.env['ab_inventory_audit_count'].browse(sorted(attempt_ids)).exists()}
        for number, values in enumerate(rows[2:], 3):
            if not any(value is not None for value in values):
                continue
            try:
                if any(isinstance(value, str) and value.startswith('=') for value in values):
                    raise ValidationError(_('Formulas are not allowed.'))
                row = dict(zip(COLUMNS, values))
                if any(type(row[key]) is not int for key in ('audit_id', 'group_id', 'attempt_id', 'revision', 'format_version')) or row['audit_id'] != self.audit_id.id:
                    raise ValidationError(_('Foreign audit or attempt identifier.'))
                attempt = attempts.get(row['attempt_id'], self.env['ab_inventory_audit_count'])
                attempt.check_access('read')
                if not attempt or attempt.audit_id != self.audit_id or attempt.line_id.id != row['group_id'] or attempt.counter_id != self.env.user:
                    raise ValidationError(_('Foreign audit or attempt identifier.'))
                if attempt.id in seen:
                    raise ValidationError(_('Duplicate count row.'))
                seen.add(attempt.id)
                if not attempt.export_token or row['token'] != attempt.export_token or row['revision'] != attempt.revision or row['format_version'] != 2 or attempt.workbook_version != 2:
                    raise ValidationError(_('The count sheet identity is invalid.'))
                if attempt.line_id.counting_revision != row['revision'] or attempt.state not in ('active', 'valid'):
                    raise ValidationError(_('Group %s changed. Cancel the attempt with a reason, request a recount and export again.', attempt.line_id.id))
                quantities = [row[key] for key in ('large_qty', 'medium_qty', 'small_qty')]
                if all(value is None for value in quantities):
                    continue
                quantities = [value if value is not None else 0 for value in quantities]
                count_quantity(attempt.line_id.product_id.sudo(), *quantities)
                if attempt.state == 'valid' and attempt.quantity_fingerprint != attempt._quantity_fingerprint(*quantities):
                    raise ValidationError(_('Confirmed quantities cannot change. Request a new count attempt.'))
                checked.append((attempt, quantities))
            except (ValidationError, AccessError, ValueError, TypeError) as error:
                errors.append(_('Row %(row)s: %(error)s', row=number, error=str(error)))
        if not checked and not errors:
            errors.append(_('The workbook contains no completed quantities. Enter explicit zero for empty stock.'))
        return digest, checked, errors

    def action_preview(self):
        digest, checked, errors = self._load_rows()
        self.write({'preview_digest': digest if not errors else False,
                    'preview': '\n'.join(errors) if errors else _('Validated rows: %s', len(checked))})
        return self.action_preview_result()

    def action_preview_result(self):
        self._scope()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'views': [(False, 'form')], 'name': _('Audit Workflow'), 'target': 'new'}

    def action_import(self):
        self._scope()
        with self.env.cr.savepoint():
            self.audit_id._lock()
            digest, checked, errors = self._load_rows()
            if errors or digest != self.preview_digest:
                raise ValidationError(_('Preview this exact workbook and resolve every row error first.'))
            lines = self.env['ab_inventory_audit_line'].browse([attempt.line_id.id for attempt, quantities in checked])
            ledger = self.audit_id._ledger(product_ids=lines.product_id.ids,
                                           group_keys=None if any(lines.mapped('physical_absence')) else set(lines.mapped('group_key')))
            invalid = []
            for attempt, quantities in checked:
                if not attempt._confirm(*quantities, digest=digest, ledger=ledger):
                    invalid.append(str(attempt.line_id.id))
            if invalid:
                self.write({'preview': _('Movement changes invalidated groups: %s. Request a recount.', ', '.join(invalid)), 'preview_digest': False})
                return self.action_preview_result()
        return {'type': 'ir.actions.act_window_close'}
