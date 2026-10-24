from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class EtaDashboard(models.Model):
    _inherit = 'ab_tax_eta_archive_sync'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, config_id=None):
        if not self.env.user.has_group('ab_tax_eta_archive.group_eta_user'):
            raise AccessError(_('You are not allowed to view the ETA dashboard.'))

        today = fields.Date.context_today(self)
        try:
            start = fields.Date.to_date(date_from) if date_from else today - timedelta(days=29)
            end = fields.Date.to_date(date_to) if date_to else today
        except (TypeError, ValueError) as exc:
            raise ValidationError(_('Choose a valid dashboard period of up to 366 days.')) from exc
        if not start or not end or end < start or (end - start).days > 365:
            raise ValidationError(_('Choose a valid dashboard period of up to 366 days.'))

        config_domain = []
        if config_id:
            try:
                selected_id = int(config_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError(_('Choose a valid ETA connection.')) from exc
            if not self.env['ab_tax_eta_archive_config'].search([('id', '=', selected_id)], limit=1):
                raise ValidationError(_('Choose a valid ETA connection.'))
            config_domain = [('config_id', '=', selected_id)]

        categories = {
            'sent_invoice': {'count': 0},
            'received_invoice': {'count': 0},
            'sent_receipt': {'count': 0},
            'received_receipt': {'count': 0},
        }
        chart_start = max(start, end - timedelta(days=13))
        daily = {}
        day = chart_start
        while day <= end:
            daily[fields.Date.to_string(day)] = {'date': fields.Date.to_string(day),
                                                  'invoices': 0, 'receipts': 0}
            day += timedelta(days=1)

        issue_domain = config_domain + [('report_date', '>=', start),
                                        ('report_date', '<=', end)]
        for kind, model_name in (
            ('invoice', 'ab_tax_eta_archive_invoice'),
            ('receipt', 'ab_tax_eta_archive_receipt'),
        ):
            groups = self.env[model_name]._read_group(
                issue_domain, ['report_date', 'direction'], ['__count'])
            for issue_date, direction, count in groups:
                category = f'{direction}_{kind}'
                categories[category]['count'] += count
                date_key = fields.Date.to_string(issue_date)
                if date_key in daily:
                    daily[date_key]['invoices' if kind == 'invoice' else 'receipts'] += count

        retrieval_domain = config_domain + [('report_date', '>=', start),
                                            ('report_date', '<=', end)]
        retrievals = {'pending': 0, 'done': 0, 'error': 0}
        for state, count in self._read_group(retrieval_domain, ['state'], ['__count']):
            retrievals[state] = count

        export_model = self.env['ab_tax_eta_archive_export']
        export_domain = issue_domain
        files = {
            'generated': export_model.search_count(export_domain),
            'sent': export_model.search_count(export_domain + [('telegram_sent_at', '!=', False)]),
            'corrections': export_model.search_count(export_domain + [('revision', '>', 1)]),
        }
        recent_errors = self.search(retrieval_domain + [('state', '=', 'error')],
                                    order='last_run_at desc, id desc', limit=5)
        latest_done = self.search(retrieval_domain + [('state', '=', 'done')],
                                  order='last_run_at desc, id desc', limit=1)
        connections = self.env['ab_tax_eta_archive_config'].search([], order='name')
        return {
            'period': {'from': fields.Date.to_string(start), 'to': fields.Date.to_string(end)},
            'connections': [{'id': config.id, 'name': config.name} for config in connections],
            'categories': categories,
            'daily': list(daily.values()),
            'retrievals': retrievals,
            'last_success': fields.Datetime.to_string(latest_done.last_run_at)
            if latest_done and latest_done.last_run_at else False,
            'files': files,
            'errors': [{
                'id': run.id,
                'date': fields.Date.to_string(run.report_date),
                'kind': run.kind,
                'direction': run.direction,
                'connection': run.config_id.name,
                'message': run.error_message or '',
            } for run in recent_errors],
        }
