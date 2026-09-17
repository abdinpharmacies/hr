import base64
import binascii
import csv
import hashlib
import io
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from ..runner.engine import validate_server


class DeployServerImport(models.TransientModel):
    _name = 'ab_deploy_server_import'
    _description = 'Import Deployment Servers'

    csv_file = fields.Binary(string='Servers CSV', required=True, attachment=False)
    filename = fields.Char()
    environment = fields.Selection([('development', 'Development'), ('test', 'Test'), ('pilot', 'Pilot'),
                                    ('production', 'Production')], required=True, default='test')
    preview = fields.Text(readonly=True)
    preview_hash = fields.Char(readonly=True)

    def _check_admin(self):
        if not self.env.user.has_group('ab_deploy.group_administrator'):
            raise AccessError(_('Only Deployment Administrators can import servers.'))
        self.check_access('write')

    def _rows(self):
        self.ensure_one()
        self._check_admin()
        try:
            data = base64.b64decode(self.csv_file, validate=True)
            if len(data) > 2_000_000:
                raise ValueError()
            reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
            allowed = {'server', 'serial', 'db_serial', 'odoo_link', 'name', 'contact', 'Area', 'timeout', 'ip'}
            if not reader.fieldnames or set(reader.fieldnames) != allowed or len(reader.fieldnames) != len(allowed):
                raise ValueError()
            rows = list(reader)
        except (ValueError, UnicodeError, csv.Error, binascii.Error) as exc:
            raise ValidationError(_('Upload a UTF-8 CSV with server, serial, db_serial, odoo_link, name, contact, Area, timeout, and ip columns (maximum 2 MB).')) from exc
        if not rows or len(rows) > 10000:
            raise ValidationError(_('The CSV must contain between 1 and 10000 server rows.'))
        seen, values = set(), []
        mapping = {'server': 'ssh_alias', 'serial': 'serial', 'db_serial': 'db_serial', 'odoo_link': 'odoo_url',
                   'name': 'name', 'contact': 'contact', 'Area': 'area', 'ip': 'hostname'}
        for row in rows:
            if None in row or any(v is None for v in row.values()):
                raise ValidationError(_('Each CSV row must have exactly the expected columns.'))
            vals = {dest: row[src].strip() for src, dest in mapping.items()}
            alias = vals['ssh_alias']
            if not alias or alias in seen:
                raise ValidationError(_('Every CSV row needs a distinct SSH alias.'))
            seen.add(alias)
            try:
                int(row['timeout'].strip())  # Validate legacy format; it is a connection timeout, not job duration.
                vals['monitor_timeout_seconds'] = 600
                validate_server(vals)
            except ValueError as exc:
                raise ValidationError(_('Invalid server settings or timeout in CSV row: %s', alias)) from exc
            vals['name'] = vals['name'] or alias
            vals['hostname'] = vals['hostname'] or alias
            values.append(vals)
        return values

    def _plan(self):
        rows = self._rows()
        Server = self.env['ab_deploy_server'].with_context(active_test=False)
        existing = {s.ssh_alias: s for s in Server.search(fields.Domain('ssh_alias', 'in', [v['ssh_alias'] for v in rows]))}
        plan = []
        for vals in rows:
            server = existing.get(vals['ssh_alias'])
            if server:
                vals['monitor_timeout_seconds'] = server.monitor_timeout_seconds
            plan.append({'id': server.id if server else False, 'before': server.read(list(vals), load=None)[0] if server else {},
                         'values': vals if server else dict(vals, code=vals['ssh_alias'], environment=self.environment)})
        return plan

    def action_preview(self):
        self.ensure_one()
        plan = self._plan()
        serialized = json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str)
        super().write({'preview': serialized, 'preview_hash': hashlib.sha256(serialized.encode()).hexdigest()})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_apply(self):
        self.ensure_one()
        plan = self._plan()
        serialized = json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str)
        if not self.preview_hash or self.preview_hash != hashlib.sha256(serialized.encode()).hexdigest():
            raise UserError(_('Preview the import again; the file, environment, or server records changed.'))
        Server = self.env['ab_deploy_server']
        Server.browse([p['id'] for p in plan if p['id']])._lock()
        # Recheck after acquiring locks before making any changes.
        if json.dumps(self._plan(), ensure_ascii=False, sort_keys=True, default=str) != serialized:
            raise UserError(_('Preview the import again; the file, environment, or server records changed.'))
        for item in plan:
            if item['id']:
                Server.browse(item['id']).write(item['values'])
            else:
                Server.create(item['values'])
        super().write({'preview_hash': False})
        return {'type': 'ir.actions.act_window_close'}

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('ab_deploy.group_administrator'):
            raise AccessError(_('Only Deployment Administrators can import servers.'))
        for vals in vals_list:
            vals.update(preview=False, preview_hash=False)
        return super().create(vals_list)

    def write(self, vals):
        self._check_admin()
        if {'preview', 'preview_hash'}.intersection(vals):
            raise AccessError(_('Import previews can only be generated by the preview action.'))
        return super().write(dict(vals, preview=False, preview_hash=False))
