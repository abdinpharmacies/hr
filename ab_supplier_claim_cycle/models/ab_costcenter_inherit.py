# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ClsCostCenters(models.Model):
    _inherit = 'ab_costcenter'

    claim_ids = fields.One2many(
        'ab_supplier_claim_cycle', 'supplier_id', string='Supplier Claims',
    )

    @api.depends('claim_ids.status', 'claim_ids.write_date',
                 'claim_ids.create_date', 'claim_ids.amount_of_check',
                 'claim_ids.claim_month', 'claim_ids.name')
    def _compute_supplier_claim_activity(self):
        for rec in self:
            claims = self.env['ab_supplier_claim_cycle'].search([
                ('supplier_id', '=', rec.id),
                ('status', '=', 'closed'),
            ], order='create_date desc')

            if not claims:
                rec.supplier_claim_activity = '<div class="ab-activity-empty o_translate_inline">No previous supplier claims.</div>'
                continue

            L = ['<div class="ab-activity-root">']
            L.append('<div class="ab-activity-table-wrap">')
            L.append('<table class="ab-activity-table"><thead><tr>'
                     '<th class="o_translate_inline">Claim #</th>'
                     '<th class="o_translate_inline">Month</th>'
                     '<th class="o_translate_inline">Completed</th>'
                     '<th class="o_translate_inline">Amount</th>'
                     '<th class="o_translate_inline">Duration</th>'
                     '<th class="o_translate_inline">Status</th>'
                     '<th class="o_translate_inline">Rejects</th>'
                     '</tr></thead><tbody>')
            for c in claims:
                month = c.claim_month.strftime('%b %Y') if c.claim_month else '—'
                amt = '{:,.0f}'.format(c.amount_of_check) if c.amount_of_check else '0'
                completed_date = c.write_date.strftime('%d/%m/%Y') if c.write_date else '—'
                duration_days = (c.write_date - c.create_date).days if c.write_date and c.create_date else None
                duration_str = '%d days' % duration_days if duration_days is not None else '—'
                rejects = self.env['ab_supplier_claim_stage_history'].search_count([
                    ('claim_id', '=', c.id),
                    ('decision', '=', 'rejected'),
                ])
                if rejects:
                    rejects_html = '\U0001f534 %d <span class="o_translate_inline">Rejects</span>' % rejects
                else:
                    rejects_html = '<span class="o_translate_inline" style="color:#9ca3af;">No Rejects</span>'
                L.append('<tr>'
                         '<td class="ab-activity-cell-id">%s</td>'
                         '<td>%s</td>'
                         '<td class="ab-activity-cell-date">%s</td>'
                         '<td class="ab-activity-cell-amount">%s</td>'
                         '<td>%s</td>'
                         '<td><span class="ab-activity-decision is-approved o_translate_inline">Completed</span></td>'
                         '<td>%s</td>'
                         '</tr>' % (c.name or '—', month, completed_date, amt, duration_str, rejects_html))
            L.append('</tbody></table>')
            L.append('</div>')
            L.append('</div>')
            rec.supplier_claim_activity = '\n'.join(L)

    @api.depends('claim_ids')
    def _compute_supplier_activity_status(self):
        ClaimCycle = self.env['ab_supplier_claim_cycle']
        top3_ids = set()
        counts = ClaimCycle.read_group(
            [], ['supplier_id'], ['supplier_id']
        )
        sorted_counts = sorted(
            counts, key=lambda x: x['supplier_id_count'], reverse=True
        )
        for item in sorted_counts[:3]:
            if item.get('supplier_id'):
                top3_ids.add(item['supplier_id'][0])
        for rec in self:
            rec.supplier_activity_status = 'active' if rec.id in top3_ids else 'non_active'

    @api.depends('claim_ids.status', 'claim_ids.amount_of_check',
                 'claim_ids.write_date', 'claim_ids.create_date')
    def _compute_supplier_performance_html(self):
        for rec in self:
            claims = self.env['ab_supplier_claim_cycle'].search([
                ('supplier_id', '=', rec.id),
            ])
            total = len(claims)
            if not total:
                rec.supplier_performance_html = self._render_empty_performance()
                continue
            closed = claims.filtered(lambda c: c.status == 'closed')
            total_amount = sum(c.amount_of_check or 0 for c in closed)

            avg_days = 0.0
            if closed:
                total_seconds = sum(
                    (c.write_date - c.create_date).total_seconds()
                    for c in closed if c.write_date and c.create_date
                )
                avg_days = total_seconds / len(closed) / 86400

            sorted_by_date = claims.sorted(
                key=lambda c: c.create_date or c.write_date or fields.Datetime.now(),
                reverse=True,
            )
            latest = sorted_by_date[0]
            last_date = latest.create_date or latest.write_date
            last_claim_days = (fields.Datetime.now() - last_date).days if last_date else 0

            accepted_decisions = self.env['ab_supplier_claim_stage_history'].search_count([
                ('claim_id.supplier_id', '=', rec.id),
                ('decision', '=', 'accepted'),
            ])
            reject_events = self.env['ab_supplier_claim_stage_history'].search_count([
                ('claim_id.supplier_id', '=', rec.id),
                ('decision', '=', 'rejected'),
            ])
            total_decisions = accepted_decisions + reject_events

            if total_decisions:
                accept_pct = round(accepted_decisions / total_decisions * 100)
                reject_pct = 100 - accept_pct
                accept_str = '%d%%' % accept_pct
                reject_str = '%d%%' % reject_pct
            else:
                accept_str = '\u2014'
                reject_str = '\u2014'

            L = ['<div class="scc-kpi-row">']
            L.append(self._kpi_card('is-total', 'fa-file-text-o', str(total), 'Total Claims'))
            avg_str = '%.1f Days' % avg_days if avg_days > 0.01 else '< 1 Day'
            L.append(self._kpi_card('is-completed', 'fa-clock-o', avg_str, 'Avg Completion'))
            last_str = '%d Days Ago' % last_claim_days if last_claim_days > 0 else 'Today'
            L.append(self._kpi_card('is-today' if last_claim_days == 0 else 'is-pending', 'fa-calendar-check-o', last_str, 'Last Claim'))

            quality_card = (
                '<div class="scc-kpi-card scc-quality-card">'
                '<div class="scc-kpi-label o_translate_inline">Workflow Quality</div>'
                '<div class="scc-quality-body">'
                '<div class="scc-quality-row">'
                '<span class="scc-quality-accept">\u2713 <span class="o_translate_inline">Accept Rate</span></span>'
                '<span class="scc-quality-pct">%s</span>'
                '</div>'
                '<div class="scc-quality-row">'
                '<span class="scc-quality-reject">\u2717 <span class="o_translate_inline">Reject Rate</span></span>'
                '<span class="scc-quality-pct">%s</span>'
                '</div>'
                '</div>'
                '</div>'
            ) % (accept_str, reject_str)
            L.append(quality_card)

            amt_str = '{:,.0f} LE'.format(total_amount) if total_amount else '0 LE'
            L.append(self._kpi_card('is-total', 'fa-money', amt_str, 'Total Amount'))
            L.append('</div>')
            rec.supplier_performance_html = '\n'.join(L)

    def _render_empty_performance(self):
        L = ['<div class="scc-kpi-row">']
        for icon, label in [
            ('fa-file-text-o', 'Total Claims'),
            ('fa-clock-o', 'Avg Completion'),
            ('fa-calendar-check-o', 'Last Claim'),
            ('fa-check-circle-o', 'Workflow Quality'),
            ('fa-money', 'Total Amount'),
        ]:
            L.append('<div class="scc-kpi-card">')
            L.append('<div class="scc-kpi-icon"><i class="fa %s" aria-hidden="true"/></div>' % icon)
            L.append('<div class="scc-kpi-label o_translate_inline">%s</div>' % label)
            L.append('<div class="scc-kpi-value" style="font-size:15px;color:#9ca3af;">—</div>')
            L.append('</div>')
        L.append('</div>')
        return '\n'.join(L)

    @api.model
    def _kpi_card(self, accent_class, icon, value, label):
        return (
            '<div class="scc-kpi-card %s">'
            '<div class="scc-kpi-icon"><i class="fa %s" aria-hidden="true"/></div>'
            '<div class="scc-kpi-label o_translate_inline">%s</div>'
            '<div class="scc-kpi-value">%s</div>'
            '</div>'
        ) % (accent_class, icon, label, value)
