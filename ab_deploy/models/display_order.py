"""Stored UI ordering only; execution recordset order is intentionally unchanged."""
from odoo import api, fields, models

STATUS_RANK = {'failed': 0, 'queued': 1, 'running': 1, 'unknown': 1,
               'cancelled': 2, 'delayed': 3, 'succeeded': 4}


def display_values(status, server):
    serial = server.serial or ''
    numeric = serial.isdecimal()
    normalized = str(int(serial)) if numeric else serial.casefold()
    # ASCII hex preserves Python's Unicode order without database collation
    # differences; a prefix keeps empty strings distinct from SQL NULL.
    return (STATUS_RANK[status], 0 if numeric else 1,
            len(normalized) if numeric else 0,
            'x' + normalized.encode('utf-8').hex(),
            'x' + (server.name or '').casefold().encode('utf-8').hex())


class TargetDisplayOrder(models.Model):
    _inherit = 'ab_deploy_target'

    display_status_rank = fields.Integer(compute='_compute_display_order', store=True, string='Status Sort Rank')
    display_serial_kind = fields.Integer(compute='_compute_display_order', store=True, string='Serial Sort Type')
    display_serial_length = fields.Integer(compute='_compute_display_order', store=True, string='Serial Sort Length')
    display_serial_value = fields.Char(compute='_compute_display_order', store=True, string='Serial Sort Value')
    display_server_name = fields.Char(compute='_compute_display_order', store=True, string='Server Name Sort Value')

    @api.depends('job_ids.state', 'request_id.state', 'server_id.serial', 'server_id.name')
    def _compute_display_order(self):
        for target in self:
            latest = target.job_ids.sorted('id', reverse=True)[:1]
            status = latest.state if latest else ('cancelled' if target.request_id.state == 'cancelled' else 'delayed')
            (target.display_status_rank, target.display_serial_kind, target.display_serial_length,
             target.display_serial_value, target.display_server_name) = display_values(status, target.server_id)


class JobDisplayOrder(models.Model):
    _inherit = 'ab_deploy_job'

    display_status_rank = fields.Integer(compute='_compute_display_order', store=True, string='Status Sort Rank')
    display_serial_kind = fields.Integer(compute='_compute_display_order', store=True, string='Serial Sort Type')
    display_serial_length = fields.Integer(compute='_compute_display_order', store=True, string='Serial Sort Length')
    display_serial_value = fields.Char(compute='_compute_display_order', store=True, string='Serial Sort Value')
    display_server_name = fields.Char(compute='_compute_display_order', store=True, string='Server Name Sort Value')

    @api.depends('state', 'server_id.serial', 'server_id.name')
    def _compute_display_order(self):
        for job in self:
            (job.display_status_rank, job.display_serial_kind, job.display_serial_length,
             job.display_serial_value, job.display_server_name) = display_values(job.state, job.server_id)
