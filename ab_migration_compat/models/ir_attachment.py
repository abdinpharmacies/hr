from odoo import fields, models
from werkzeug.exceptions import NotFound


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    migration_file_missing = fields.Boolean(string='Original File Unavailable', readonly=True, copy=False)
    migration_source_path = fields.Char(string='Original Filestore Path', readonly=True, copy=False)
    migration_source_checksum = fields.Char(string='Original File Checksum', readonly=True, copy=False)
    migration_source_size = fields.Integer(string='Original File Size', readonly=True, copy=False)

    def _to_http_stream(self):
        self.ensure_one()
        if self.migration_file_missing:
            raise NotFound(self.env._('The original attachment file was unavailable during migration. Restore it from the source backup.'))
        return super()._to_http_stream()

    def write(self, values):
        if values.get('raw') or values.get('datas'):
            values = dict(values, migration_file_missing=False)
        return super().write(values)
