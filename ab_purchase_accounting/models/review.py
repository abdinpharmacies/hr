from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .purchase import _money


class PurchaseAccountingReview(models.Model):
    _name = 'ab_purchase_accounting_review'
    _description = 'Purchase Accounting Review Log'
    _inherit = ['mail.thread']
    _rec_name = 'document_reference'
    _order = 'captured_at desc, id desc'

    company_id = fields.Many2one('res.company', required=True, readonly=True, ondelete='restrict')
    branch_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict', index=True)
    document_model = fields.Char(required=True, readonly=True)
    document_id = fields.Integer(required=True, readonly=True)
    document_reference = fields.Char(required=True, readonly=True)
    document_date = fields.Date(readonly=True)
    event_type = fields.Selection([
        ('receipt', 'Purchase Receipt'),
        ('return', 'Supplier Return'),
        ('financial_credit', 'Financial Credit Notice'),
        ('financial_debit', 'Financial Debit Notice'),
        ('other_receipt', 'Non-purchase Receipt'),
    ], required=True, readonly=True)
    captured_by = fields.Many2one('res.users', required=True, readonly=True, ondelete='restrict')
    captured_at = fields.Datetime(required=True, readonly=True)
    total_amount = fields.Float(digits=(16, 2), readonly=True)
    tax_amount = fields.Float(digits=(16, 2), readonly=True)
    inventory_amount = fields.Float(digits=(16, 2), readonly=True)
    snapshot = fields.Json(required=True, readonly=True, copy=False)
    issues = fields.Text(readonly=True)
    invoice_details = fields.Html(compute='_compute_details')
    proposed_entries = fields.Html(compute='_compute_details')
    review_state = fields.Selection([
        ('pending', 'Pending Review'), ('reviewed', 'Reviewed'), ('needs_attention', 'Needs Attention'),
    ], required=True, default='pending', readonly=True, tracking=True)
    review_note = fields.Text(tracking=True)
    reviewed_by = fields.Many2one('res.users', readonly=True, ondelete='restrict')
    reviewed_at = fields.Datetime(readonly=True)

    _document_unique = models.Constraint(
        'UNIQUE(document_model, document_id)',
        'A finalized document can have only one accounting review log.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Review logs are created only when a business document is finalized.'))

    def unlink(self):
        raise AccessError(_('Accounting review logs cannot be deleted.'))

    def _check_reviewer(self):
        self.check_access('write')
        if not (self.env.user.has_group('base.group_system')
                or self.env.user.has_group('ab_accounting.group_ab_accounting_reviewer')):
            raise AccessError(_('Accounting reviewer access is required.'))

    def write(self, vals):
        self._check_reviewer()
        if set(vals) - {'review_note'}:
            raise AccessError(_('Captured values cannot be changed. Use the review actions.'))
        return super().write(vals)

    def action_mark_reviewed(self):
        return self._mark_review('reviewed')

    def action_needs_attention(self):
        return self._mark_review('needs_attention')

    def _mark_review(self, state):
        self._check_reviewer()
        return super().write({
            'review_state': state,
            'reviewed_by': self.env.uid,
            'reviewed_at': fields.Datetime.now(),
        })

    def action_open_document(self):
        self.ensure_one()
        self.check_access('read')
        document = self.env[self.document_model].browse(self.document_id).exists()
        if not document:
            raise UserError(_('The source document is no longer available.'))
        document.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'res_model': document._name,
            'res_id': document.id, 'view_mode': 'form',
        }

    @api.model
    def _capture_if_enabled(self, document):
        document.ensure_one()
        if document._name not in {'ab_purchase_header', 'ab_purchase_notice_header', 'ab_purchase_ob_header'}:
            raise ValidationError(_('Unsupported review document.'))
        document.check_access('write')
        user = self.env.user
        if not (user.has_group('base.group_system')
                or user.has_group('ab_purchase.group_ab_purchase_manager')
                or (document._name == 'ab_purchase_ob_header'
                    and user.has_group('ab_inventory.group_inventory_manager'))):
            raise AccessError(_('Only authorized document managers can capture accounting reviews.'))
        self.env['ab_inventory_process']._check_store(document.store_id.id)
        document.lock_for_update()
        document.invalidate_recordset(['status'])
        if document.status != 'saved':
            raise ValidationError(_('Finalize the document before capturing its accounting review.'))
        if document._name == 'ab_purchase_ob_header' and document.purpose == 'opening':
            return False
        config = self.env['ab_purchase_accounting_config'].search(fields.Domain([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id), ('branch_id', '=', document.store_id.id),
            ('activation_date', '<=', document.doc_date or fields.Date.context_today(document)),
        ]), order='activation_date desc, id desc', limit=1)
        if not config or config.processing_mode != 'review':
            return False
        config.check_access('read')
        config._check_configuration()
        values = self._prepare_snapshot(document, config)
        existing = self.sudo().search(fields.Domain([
            ('document_model', '=', document._name), ('document_id', '=', document.id),
        ]), limit=1)
        if existing:
            if (existing.company_id != self.env.company or existing.branch_id != document.store_id
                    or existing.snapshot != values['snapshot']):
                raise ValidationError(_('This document already has a different accounting snapshot.'))
            return True
        super(PurchaseAccountingReview, self.sudo()).create(values)
        return True

    def _prepare_snapshot(self, document, config):
        document = document.with_context(lang='en_US')
        config = config.sudo().with_context(lang='en_US')
        is_purchase = document._name == 'ab_purchase_header'
        is_other = document._name == 'ab_purchase_ob_header'
        total = _money((document.net_invoice or document.total_cost) if is_purchase else document.total_cost)
        tax = _money((document.net_tax or document.total_tax) if is_purchase
                     else document.total_tax if is_other else document.total_taxes_value)
        inventory = total if is_other else _money(total - tax)
        event = 'receipt' if is_purchase else 'other_receipt' if is_other else 'return'
        sign = -1 if event in {'return', 'financial_credit'} else 1
        offset = config.supplier_account_id
        if is_other:
            offset = config.receipt_account_ids.filtered(
                lambda row: row.receipt_type_id == document.receipt_type_id
            )[:1].offset_account_id
        entries = []
        issues = []
        if is_purchase and (_money(document.total_cost) != total or _money(document.total_tax) != tax):
            issues.append(_('Entered invoice totals differ from calculated line totals.'))
        for role, account, amount in [
            ('inventory', config.inventory_account_id, inventory * sign),
            ('tax', config.tax_account_id, 0 if is_other else tax * sign),
            ('offset' if is_other else 'supplier', offset, -total * sign),
        ]:
            if not amount:
                continue
            if not account:
                issues.append(_('Missing account mapping: %s') % self._role_label(role))
            entries.append({
                'role': role, 'account_id': account.id or False,
                'account_name': account.display_name or '',
                'debit': max(amount, 0), 'credit': max(-amount, 0),
            })
        try:
            config._check_company_records()
            config._check_posting_user()
        except UserError as error:
            issues.append(str(error))
        invoice_lines = []
        for line in document.line_ids.sorted('id'):
            source = line.source_id
            source_snapshot = source._get_posting_snapshot()
            conversion = source._get_conversion_basis()
            invoice_lines.append({
                'line_id': line.id, 'source_id': source.id, 'product_id': source.product_id.id,
                'product': source.product_id.display_name, 'product_code': source.product_id.code,
                'quantity': line.qty, 'bonus': 0 if is_other else line.bonus,
                'unit': line.uom_id.display_name, 'unit_id': line.uom_id.id,
                'small_units_per_large': conversion['small'],
                'medium_units_per_large': conversion['medium'],
                'source_identity': source.source_identity, 'no_expiry': source.no_expiry,
                'expiry': str(source.exp_date) if source.exp_date else False,
                'selling_price': source.price, 'purchase_price': source.purchase_price,
                'discount_percentage': source.extra_discount_percentage,
                'unit_cost': source.unit_cost, 'unit_tax': source.unit_taxes_value,
                'taxes': source_snapshot['taxes'] if source_snapshot else [
                    {'id': tax.id, 'name': tax.name, 'percentage': tax.percentage,
                     'apply_on_total': tax.apply_on_total} for tax in source.taxes_ids.sorted('id')],
            })
        snapshot = {
            'database': self.env.cr.dbname, 'configuration_id': config.id,
            'company_id': self.env.company.id, 'branch_id': document.store_id.id,
            'branch_code': document.store_id.code, 'document_model': document._name,
            'document_id': document.id, 'reference': document.doc_code,
            'date': str(document.doc_date) if document.doc_date else False,
            'event': event, 'total': total, 'tax': tax, 'inventory': inventory,
            'header_discount': document.total_extra_discount if is_purchase else 0,
            'supplier_id': False if is_other else document.supplier_id.id,
            'supplier_name': False if is_other else document.supplier_id.display_name,
            'lines': invoice_lines, 'entries': entries,
        }
        return {
            'company_id': self.env.company.id, 'branch_id': document.store_id.id,
            'document_model': document._name, 'document_id': document.id,
            'document_reference': document.doc_code or str(document.id),
            'document_date': document.doc_date, 'event_type': event,
            'captured_by': self.env.uid, 'captured_at': fields.Datetime.now(),
            'total_amount': total, 'tax_amount': tax, 'inventory_amount': inventory,
            'snapshot': snapshot, 'issues': '\n'.join(dict.fromkeys(issues)),
        }

    def _role_label(self, role):
        return {'inventory': _('Inventory'), 'tax': _('Tax'),
                'supplier': _('Supplier'), 'offset': _('Receipt Offset')}[role]

    @staticmethod
    def _render_table(headers, rows):
        heading = Markup('').join(Markup('<th>%s</th>') % value for value in headers)
        body = Markup('').join(
            Markup('<tr>%s</tr>') % Markup('').join(Markup('<td>%s</td>') % value for value in row)
            for row in rows
        )
        return Markup('<table class="table table-sm"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (heading, body)

    @api.depends('snapshot')
    @api.depends_context('lang')
    def _compute_details(self):
        for rec in self:
            snapshot = rec.snapshot or {}
            rec.invoice_details = self._render_table(
                [_('Product'), _('Quantity'), _('Bonus'), _('Unit'), _('Purchase Price'), _('Discount %'), _('Unit Tax')],
                [[line[key] for key in ('product', 'quantity', 'bonus', 'unit', 'purchase_price',
                                       'discount_percentage', 'unit_tax')]
                 for line in snapshot.get('lines', [])],
            )
            rec.proposed_entries = self._render_table(
                [_('Purpose'), _('Account'), _('Debit'), _('Credit')],
                [[self._role_label(line['role']), line['account_name'] or _('Not configured'),
                  '%.2f' % line['debit'], '%.2f' % line['credit']] for line in snapshot.get('entries', [])],
            )
