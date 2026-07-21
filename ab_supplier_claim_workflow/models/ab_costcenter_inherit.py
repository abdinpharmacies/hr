# -*- coding: utf-8 -*-

from odoo import _, models, fields, api


class ClsCostCenters(models.Model):
    _inherit = 'ab_costcenter'

    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('supplier_claim_filter'):
            mapped = self.env['ab.supplier.mapping'].sudo().search([]).mapped('supplier_id').ids
            if mapped:
                args = list(args or []) + [('id', 'in', mapped)]
        return super(ClsCostCenters, self).name_search(name, args, operator, limit)

    supplier_type = fields.Selection(
        string='Supplier Type',
        selection=[
            ('advance_payment', 'Advance Payment'),
            ('withholding_tax', 'Withholding Tax'),
            ('non_taxable', 'Non-Taxable'),
        ],
        copy=False,
    )
    region = fields.Selection(
        string='Region',
        selection=[
            ('north', 'North'),
            ('south', 'South'),
        ],
        copy=False,
    )
    section = fields.Selection(
        string='Section',
        selection=[
            ('medicine', 'ادوية'),
            ('cosmetics', 'تجميل'),
            ('medical_preps', 'مستحضرات طبية'),
            ('supplies', 'مستلزمات'),
            ('import_medicine', 'مستورد ادوية'),
            ('import_cosmetics', 'مستورد تجميل'),
        ],
        copy=False,
    )

    claim_ids = fields.One2many(
        'ab_supplier_claim_cycle', 'supplier_id', string='Supplier Claims',
    )
    delegate_phone_ids = fields.One2many(
        'ab.delegate.phone', 'partner_id', string='Delegate Phones',
    )
    all_delegate_phones = fields.Char(
        string='All Delegate Phones', compute='_compute_all_delegate_phones', store=False,
    )

    @api.depends('delegate_phone_ids.name')
    def _compute_all_delegate_phones(self):
        for rec in self:
            phones = rec.delegate_phone_ids.mapped('name')
            rec.all_delegate_phones = ', '.join(phones) if phones else ''

    supplier_claim_activity = fields.Html(
        string='Supplier Claim Activity', compute='_compute_supplier_claim_activity', store=False,
    )
    supplier_activity_status = fields.Char(
        string='Supplier Activity Status', compute='_compute_supplier_activity_status', store=False,
    )
    supplier_performance_html = fields.Html(
        string='Supplier Performance', compute='_compute_supplier_performance_html', store=False,
    )

    @api.depends('claim_ids.status', 'claim_ids.write_date',
                 'claim_ids.create_date', 'claim_ids.amount_of_check')
    @api.depends_context('lang')
    def _compute_supplier_claim_activity(self):
        for rec in self:
            claims = self.env['ab_supplier_claim_cycle'].search([
                ('supplier_id', '=', rec.id),
                ('status', '=', 'closed'),
            ], order='create_date desc')

            if not claims:
                rec.supplier_claim_activity = '<div class="ab-activity-empty">%s</div>' % _(
                    'No previous supplier claims.'
                )
                continue

            L = ['<div class="ab-activity-root">']
            L.append('<div class="ab-activity-table-wrap">')
            L.append('<table class="ab-activity-table"><thead><tr>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '<th>%s</th>'
                     '</tr></thead><tbody>' % (
                         _('Claim #'),
                         _('Month'),
                         _('Completed'),
                         _('Amount'),
                         _('Duration'),
                         _('Status'),
                         _('Rejects'),
                     ))
            for c in claims:
                month = c.claim_month.strftime('%b %Y') if c.claim_month else '—'
                amt = '{:,.0f}'.format(c.amount_of_check) if c.amount_of_check else '0'
                completed_date = c.write_date.strftime('%d/%m/%Y') if c.write_date else '—'
                duration_days = (c.write_date - c.create_date).days if c.write_date and c.create_date else None
                duration_str = _('%d days') % duration_days if duration_days is not None else '—'
                rejects = self.env['ab_supplier_claim_stage_history'].search_count([
                    ('claim_id', '=', c.id),
                    ('decision', '=', 'rejected'),
                ])
                if rejects:
                    rejects_html = '\U0001f534 %d <span>%s</span>' % (rejects, _('Rejects'))
                else:
                    rejects_html = '<span style="color:#9ca3af;">%s</span>' % _('No Rejects')
                L.append('<tr>'
                         '<td class="ab-activity-cell-id">%s</td>'
                         '<td>%s</td>'
                         '<td class="ab-activity-cell-date">%s</td>'
                         '<td class="ab-activity-cell-amount">%s</td>'
                         '<td>%s</td>'
                         '<td><span class="ab-activity-decision is-approved">%s</span></td>'
                         '<td>%s</td>'
                         '</tr>' % (c.name or '—', month, completed_date, amt, duration_str, _('Completed'), rejects_html))
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
    @api.depends_context('lang')
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
            L.append(self._kpi_card('is-total', 'fa-file-text-o', str(total), _('Total Claims')))
            avg_str = _('%0.1f Days') % avg_days if avg_days > 0.01 else _('< 1 Day')
            L.append(self._kpi_card('is-completed', 'fa-clock-o', avg_str, _('Avg Completion')))
            last_str = _('%d Days Ago') % last_claim_days if last_claim_days > 0 else _('Today')
            L.append(self._kpi_card('is-today' if last_claim_days == 0 else 'is-pending', 'fa-calendar-check-o', last_str, _('Last Claim')))

            quality_card = (
                '<div class="scc-kpi-card scc-quality-card">'
                '<div class="scc-kpi-label">%s</div>'
                '<div class="scc-quality-body">'
                '<div class="scc-quality-row">'
                '<span class="scc-quality-accept">\u2713 <span>%s</span></span>'
                '<span class="scc-quality-pct">%s</span>'
                '</div>'
                '<div class="scc-quality-row">'
                '<span class="scc-quality-reject">\u2717 <span>%s</span></span>'
                '<span class="scc-quality-pct">%s</span>'
                '</div>'
                '</div>'
                '</div>'
            ) % (_('Workflow Quality'), _('Accept Rate'), accept_str, _('Reject Rate'), reject_str)
            L.append(quality_card)

            amt_str = '{:,.0f} LE'.format(total_amount) if total_amount else '0 LE'
            L.append(self._kpi_card('is-total', 'fa-money', amt_str, _('Total Amount')))
            L.append('</div>')
            rec.supplier_performance_html = '\n'.join(L)

    def _render_empty_performance(self):
        L = ['<div class="scc-kpi-row">']
        for icon, label in [
            ('fa-file-text-o', _('Total Claims')),
            ('fa-clock-o', _('Avg Completion')),
            ('fa-calendar-check-o', _('Last Claim')),
            ('fa-check-circle-o', _('Workflow Quality')),
            ('fa-money', _('Total Amount')),
        ]:
            L.append('<div class="scc-kpi-card">')
            L.append('<div class="scc-kpi-icon"><i class="fa %s" aria-hidden="true"/></div>' % icon)
            L.append('<div class="scc-kpi-label">%s</div>' % label)
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
