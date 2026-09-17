import base64
import hashlib
from datetime import datetime, timezone

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class DeployLogPart(models.Model):
    _name = 'ab_deploy_log_part'
    _description = 'Deployment Odoo Log Part'
    _order = 'id'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True, ondelete='restrict', index=True)
    name = fields.Char(required=True, readonly=True)
    kind = fields.Selection([('odoo', 'Odoo Log'), ('command', 'Command Output')], default='odoo', required=True, readonly=True)
    byte_offset = fields.Char(required=True, readonly=True)
    byte_size = fields.Integer(required=True, readonly=True)
    checksum = fields.Char(required=True, readonly=True)
    data = fields.Binary(string='Download', attachment=True, readonly=True)
    _unique_offset = models.Constraint('UNIQUE(job_id, kind, byte_offset)', 'An Odoo log chunk can be stored only once.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Log parts can only be created by the deployment workflow.'))

    def write(self, vals):
        raise AccessError(_('Captured Odoo logs cannot be modified.'))

    def unlink(self):
        raise AccessError(_('Captured Odoo logs cannot be deleted.'))

    @api.model
    def _store(self, job, offset, data, kind='odoo'):
        digest = hashlib.sha256(data).hexdigest()
        existing = self.sudo().search(fields.Domain('job_id', '=', job.id) & fields.Domain('byte_offset', '=', str(offset)) & fields.Domain('kind', '=', kind), limit=1)
        if existing:
            if existing.checksum != digest:
                raise ValueError('Remote log chunk changed')
            return existing
        return super(DeployLogPart, self.sudo()).create({
            'job_id': job.id, 'kind': kind, 'name': f'{job.job_key}-{kind}-{offset:012d}.log',
            'byte_offset': str(offset), 'byte_size': len(data), 'checksum': digest,
            'data': base64.b64encode(data)})


class DeployJobLogs(models.Model):
    _inherit = 'ab_deploy_job'

    odoo_log_status = fields.Selection([
        ('disabled', 'Not Requested'), ('pending', 'Collecting'), ('done', 'Collected'),
        ('warning', 'Collected with Warnings'), ('error', 'Collection Error')],
        string='Odoo Log Collection', default='disabled', readonly=True)
    odoo_log_error = fields.Text(string='Log Collection Notes', readonly=True)
    odoo_log_preview = fields.Text(string='Recent Odoo Warnings and Errors', readonly=True)
    odoo_log_started_at = fields.Datetime(string='Log Capture Start', readonly=True)
    odoo_log_finished_at = fields.Datetime(string='Log Capture End', readonly=True)
    odoo_log_offset = fields.Char(string='Downloaded Bytes', default='0', readonly=True)
    odoo_log_checked_at = fields.Datetime(readonly=True)
    odoo_log_failures = fields.Integer(default=0, readonly=True)
    odoo_log_part_ids = fields.One2many('ab_deploy_log_part', 'job_id', string='Odoo Log Parts', readonly=True, domain=[('kind', '=', 'odoo')])

    def _accept_log_chunk(self, result):
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {'odoo_log_checked_at': now}
        meta = result.get('capture_meta')
        if not meta:
            failures = self.odoo_log_failures + 1
            vals.update(odoo_log_failures=failures,
                        odoo_log_error=_('Odoo log collection is unavailable. Use Recover Deployment Jobs to retry.'))
            if failures >= 5:
                vals['odoo_log_status'] = 'error'
            self._set(vals)
            return
        data = result['capture_chunk']
        offset = int(self.odoo_log_offset or '0')
        if result.get('capture_offset') != offset:
            return  # A delayed response may never advance a different cursor.
        if meta['state'] != 'collecting' and meta['size'] < offset:
            self._set({'odoo_log_status': 'error', 'odoo_log_error': _('The captured Odoo log was truncated or replaced. Existing downloaded parts were preserved.')})
            return
        if data:
            try:
                self.env['ab_deploy_log_part']._store(self, offset, data)
            except ValueError:
                self._set({'odoo_log_status': 'error', 'odoo_log_error': _('The captured Odoo log changed. Existing downloaded parts were preserved.')})
                return
            offset += len(data)
            vals.update(odoo_log_offset=str(offset), odoo_log_failures=0,
                        odoo_log_preview=((self.odoo_log_preview or '').encode() + data)[-65536:].decode(errors='replace'))
        elif meta['size'] > offset or (self.state in ('succeeded', 'failed', 'cancelled') and meta['state'] == 'collecting'):
            vals['odoo_log_failures'] = self.odoo_log_failures + 1
        else:
            vals['odoo_log_failures'] = 0
        translated_notes = {
            'Odoo log is missing or unreadable; some entries may be unavailable.': _('Odoo log is missing or unreadable; some entries may be unavailable.'),
            'Log truncation detected; entries between polls may be missing.': _('Log truncation detected; entries between polls may be missing.'),
            'Odoo log path disappeared or became unreadable during capture.': _('Odoo log path disappeared or became unreadable during capture.'),
            'Log rotation detected; entries written to older files after rotation may be missing.': _('Log rotation detected; entries written to older files after rotation may be missing.'),
            'Log reading failed; capture may be incomplete.': _('Log reading failed; capture may be incomplete.'),
            'Capture did not start before command execution.': _('Capture did not start before command execution.'),
            'Execution wrapper exited before log capture started.': _('Execution wrapper exited before log capture started.'),
            'Execution wrapper disappeared; exact end boundary is unavailable.': _('Execution wrapper disappeared; exact end boundary is unavailable.'),
            'Odoo log collector failed.': _('Odoo log collector failed.'),
            'Log collector could not start; check the configured Python interpreter and permissions.': _('Log collector could not start; check the configured Python interpreter and permissions.'),
        }
        warnings = meta.get('warnings', [])
        vals['odoo_log_error'] = '\n'.join(translated_notes.get(str(w), str(w)) for w in warnings[:10])[:8192] if isinstance(warnings, list) else _('Invalid log collection notes.')
        for source, destination in (('started_at', 'odoo_log_started_at'), ('finished_at', 'odoo_log_finished_at')):
            try:
                stamp = datetime.fromisoformat(meta.get(source, '').replace('Z', '+00:00'))
                vals[destination] = stamp.astimezone(timezone.utc).replace(tzinfo=None)
            except (TypeError, ValueError, AttributeError):
                pass
        if meta['state'] != 'collecting' and offset >= meta['size']:
            vals['odoo_log_status'] = {'done': 'done', 'warning': 'warning', 'error': 'error'}[meta['state']]
        elif vals.get('odoo_log_failures', 0) >= 5:
            vals.update(odoo_log_status='error', odoo_log_error=_('Odoo log collection stopped making progress. Use recovery to check it again.'))
        self._set(vals)
