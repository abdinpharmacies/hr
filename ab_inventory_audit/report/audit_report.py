from odoo import api, models, _


class AuditReport(models.AbstractModel):
    _name = 'report.ab_inventory_audit.results'
    _description = 'Inventory Audit Report'

    @api.model
    def _sections(self, audit):
        audit.check_access('read')
        audit._check_branch(audit.store_id)
        lines = self.env['ab_inventory_audit_line'].search([('audit_id', '=', audit.id)])
        counts = self.env['ab_inventory_audit_count'].search([('line_id', 'in', lines.ids)])
        financial = self.env.user.has_group('ab_inventory_audit.group_financial') or self.env.user.has_group('base.group_system')
        sections = [
            (_('Results and Coverage'), [_('Group ID'), _('Accepted Attempt'), _('Physical Absence'), _('Product'), _('Expiry'), _('Price'), _('Status'), _('Reference'),
                                       _('Physical'), _('Discrepancy'), _('Review / Exclusion')],
             [[line.id, line.accepted_count_id.id or '', _('Yes') if line.physical_absence else '',
               line.product_id.display_name or line.product_code, str(line.exp_date or ''), line.comparison_price,
               dict(line._fields['state']._description_selection(self.env))[line.state], line.reference_qty,
               line.counted_qty if line.accepted_count_id else '', line.discrepancy if line.accepted_count_id else '',
               line.exclusion_reason or line.review_reason or ''] for line in lines]),
            (_('Count Attempts'), [_('Group ID'), _('Attempt ID'), _('Accepted'), _('Expiry'), _('Comparison Price'), _('Product'), _('Counter'), _('Started'), _('Finished'), _('Status'),
                                   _('Quantity'), _('Reference'), _('Reason')],
             [[count.line_id.id, count.id, _('Yes') if count == count.line_id.accepted_count_id else '',
               str(count.line_id.exp_date or ''), count.line_id.comparison_price,
               count.line_id.product_id.display_name or count.line_id.product_code, count.counter_id.name, str(count.started_at),
               str(count.ended_at or ''), dict(count._fields['state']._description_selection(self.env))[count.state],
               count.quantity if count.state != 'active' else '', count.reference_qty, '\n'.join(filter(None, [count.notes, count.reason, count.resolution_reason]))] for count in counts]),
            (_('History'), [_('Actor'), _('Time'), _('Action'), _('Revision'), _('Reason')],
             [[event.actor_id.name, str(event.occurred_at), event.action, event.revision, event.reason or '']
              for event in audit.event_ids]),
        ]
        moves_rows = []
        all_source_ids = set()
        for line in lines.filtered('accepted_count_id'):
            boundary = line.accepted_count_id.sudo().boundary
            all_source_ids.update(int(source_id) for source_id in boundary['sources'])
            all_source_ids.update(line.sudo().source_ids.source_id.ids)
        movements = self.env['ab_inventory'].sudo().search([
            ('store_id', '=', audit.store_id.id), ('source_id', 'in', sorted(all_source_ids)), ('status', '=', 'saved')], order='id')
        for line in lines.filtered('accepted_count_id'):
            boundary = line.accepted_count_id.sudo().boundary
            old_ids = {item[0] for item in boundary['moves']}
            source_ids = set(map(int, boundary['sources'])) | set(line.sudo().source_ids.source_id.ids)
            later = movements.filtered(lambda movement: movement.source_id.id in source_ids and movement.id not in old_ids and (not audit.posted_at or movement.saved_at <= audit.posted_at))
            for movement in later:
                moves_rows.append([line.id, line.accepted_count_id.id, str(line.exp_date or ''), line.comparison_price, line.product_id.display_name or line.product_code, movement.id, str(movement.saved_at), movement.qty,
                                   movement.model_ref, movement.res_id])
        sections.append((_('Movements After Accepted Count'), [_('Group ID'), _('Accepted Attempt'), _('Expiry'), _('Comparison Price'), _('Product'), _('Movement'), _('Posted At'),
                        _('Quantity'), _('Origin'), _('Reference')], moves_rows))
        if financial:
            sources = lines.source_ids
            sections.append((_('Source Allocation and Valuation'), [_('Group ID'), _('Accepted Attempt'), _('Expiry'), _('Comparison Price'), _('Product'), _('Source'), _('Reference'),
                             _('Adjustment'), _('Smallest Unit Cost'), _('Value'), _('Reason')],
                             [[source.line_id.id, source.line_id.accepted_count_id.id or '',
                               str(source.line_id.exp_date or ''), source.line_id.comparison_price, source.line_id.product_id.display_name or source.line_id.product_code, source.source_id.id or _('New Source'),
                               source.reference_qty, source.allocation_qty, source.frozen_cost, source.frozen_value,
                               source.allocation_reason or source.zero_cost_reason or ''] for source in sources]))
            adjustments = audit.adjustment_ids
            sections.append((_('Posting Reconciliation'), [_('Group ID'), _('Accepted Attempt'), _('Source'), _('Before'), _('Adjustment'), _('After'),
                             _('Stock Movement'), _('Value')],
                             [[adjustment.audit_source_id.line_id.id, adjustment.audit_source_id.line_id.accepted_count_id.id, adjustment.source_id.id, adjustment.balance_before, adjustment.qty,
                               adjustment.balance_before + adjustment.qty, adjustment.movement_id.id,
                               adjustment.value] for adjustment in adjustments]))
            surplus = sum(source.frozen_value for source in sources if source.allocation_qty > 0)
            shortage = -sum(source.frozen_value for source in sources if source.allocation_qty < 0)
            sections.append((_('Approval and Accounting'), [_('Approval Revision'), _('Approver'), _('Approved At'),
                             _('Surplus Value'), _('Shortage Value'), _('Surplus Journal'), _('Shortage Journal')],
                             [[audit.approval_revision, audit.approved_by.name or '', str(audit.approved_at or ''),
                               surplus, shortage, audit.surplus_journal_id.id or '', audit.shortage_journal_id.id or '']]))
        coverage = self.env['ab_inventory_audit_coverage'].search([('audit_id', '=', audit.id)])
        observations = self.env['ab_inventory_audit_observation'].search([('audit_id', '=', audit.id)])
        sections.append((_('Product Coverage'), [_('Product'), _('Scope Origin'), _('Decision'), _('Status'), _('Reason')],
                         [[item.product_id.display_name or item.product_id.code,
                           dict(item._fields['origin']._description_selection(self.env))[item.origin],
                           dict(item._fields['decision']._description_selection(self.env))[item.decision],
                           dict(item._fields['state']._description_selection(self.env))[item.state],
                           item.decision_reason or ''] for item in coverage]))
        sections.append((_('Stock Observations'), [_('Observation ID'), _('Product'), _('Counter'), _('Quantity'),
                         _('Unit'), _('Expiry'), _('Notes'), _('Decision'), _('Group ID'), _('Reason')],
                         [[item.id, item.product_id.display_name or item.product_id.code, item.counter_id.name, item.quantity,
                           item.uom_id.display_name, str(item.exp_date or ''), item.notes,
                           dict(item._fields['state']._description_selection(self.env))[item.state],
                           item.line_id.id or '', item.decision_reason or ''] for item in observations]))
        sections.append((_('Allocation Review'), [_('Group ID'), _('Accepted Attempt'), _('Unresolved'),
                         _('Stock Conflict'), _('Resolution')],
                         [[line.id, line.accepted_count_id.id or '', _('Yes') if line.allocation_unresolved else '',
                           line.allocation_issue or '', line.allocation_resolution or '']
                          for line in lines if line.allocation_issue]))
        return sections

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['ab_inventory_audit'].browse(docids)
        docs.check_access('read')
        return {'doc_ids': docs.ids, 'doc_model': docs._name, 'docs': docs,
                'sections': {audit.id: self._sections(audit) for audit in docs}}


class AuditXlsx(models.AbstractModel):
    _name = 'report.ab_inventory_audit.results_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Inventory Audit XLSX Report'

    def _get_objs_for_report(self, docids, data):
        return self.env['ab_inventory_audit'].browse(docids or self.env.context.get('active_ids', []))

    def generate_xlsx_report(self, workbook, data, audits):
        audits.check_access('read')
        heading = workbook.add_format({'bold': True})
        for audit in audits:
            for index, (title, columns, rows) in enumerate(self.env['report.ab_inventory_audit.results']._sections(audit)):
                sheet = workbook.add_worksheet('%s-%s' % (audit.id, index + 1))
                sheet.write_string(0, 0, audit.name, heading)
                sheet.write_string(1, 0, audit.store_id.display_name)
                sheet.write_string(2, 0, title, heading)
                sheet.write_row(3, 0, columns, heading)
                for row_index, row in enumerate(rows, 4):
                    for col_index, value in enumerate(row):
                        if isinstance(value, str):
                            sheet.write_string(row_index, col_index, value)
                        else:
                            sheet.write(row_index, col_index, value)
                sheet.freeze_panes(4, 1)
                sheet.set_column(0, len(columns) - 1, 22)


class AuditCountSheet(models.AbstractModel):
    _name = 'report.ab_inventory_audit.count_sheet'
    _description = 'Audit Count Sheet'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['ab_inventory_audit'].browse(docids)
        docs.check_access('read')
        for audit in docs:
            audit._check_branch(audit.store_id)
        return {'doc_ids': docs.ids, 'doc_model': docs._name, 'docs': docs,
                'groups': {audit.id: self.env['ab_inventory_audit_line'].search([('audit_id', '=', audit.id)]) for audit in docs},
                'coverage': {audit.id: [[item.product_id.display_name or item.product_id.code,
                    dict(item._fields['origin']._description_selection(self.env))[item.origin],
                    dict(item._fields['state']._description_selection(self.env))[item.state], item.decision_reason or '']
                    for item in self.env['ab_inventory_audit_coverage'].search([('audit_id', '=', audit.id)])] for audit in docs}}
