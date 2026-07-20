import base64
import binascii
import io
import mimetypes
import os
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.mimetypes import guess_mimetype

from .training_category import TRAINING_FILE_TYPES


POWERPOINT_MIMETYPES = {
    'application/vnd.ms-powerpoint',
    'application/vnd.ms-powerpoint.presentation.macroenabled.12',
    'application/vnd.ms-powerpoint.slideshow.macroenabled.12',
    'application/vnd.ms-powerpoint.template.macroenabled.12',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
    'application/vnd.openxmlformats-officedocument.presentationml.template',
}
POWERPOINT_ARCHIVE_EXTENSIONS = {'.pptx', '.ppsx', '.potx', '.pptm', '.ppsm', '.potm'}
POWERPOINT_ARCHIVE_MIMETYPES = {'application/octet-stream', 'application/zip'}
POWERPOINT_LEGACY_EXTENSIONS = {'.ppt', '.pps', '.pot'}
POWERPOINT_LEGACY_MIMETYPES = {
    'application/cdfv2',
    'application/msword',
    'application/x-ole-storage',
}


class TrainingMaterial(models.Model):
    _name = 'ab.training.material'
    _description = 'Training Material'
    _rec_name = 'file_name'
    _order = 'uploaded_at desc, id desc'
    _check_company_auto = True

    task_id = fields.Many2one(
        'ab.training.task',
        required=True,
        ondelete='cascade',
        check_company=True,
        index=True,
    )
    task_title = fields.Char(related='task_id.name', store=True, readonly=True)
    task_type_id = fields.Many2one(related='task_id.task_type_id', store=True, readonly=True)
    category_id = fields.Many2one(related='task_id.category_id', store=True, readonly=True)
    member_id = fields.Many2one(related='task_id.member_id', store=True, readonly=True)
    company_id = fields.Many2one(related='task_id.company_id', store=True, readonly=True)
    file_data = fields.Binary(
        string='File',
        required=True,
        attachment=True,
        copy=False,
    )
    file_name = fields.Char(required=True, copy=False, index=True)
    accepted_file_extensions = fields.Char(
        string='Accepted File Extensions',
        readonly=True,
        copy=False,
    )
    file_type = fields.Selection(
        TRAINING_FILE_TYPES,
        readonly=True,
        copy=False,
        index=True,
    )
    mimetype = fields.Char(string='MIME Type', readonly=True, copy=False)
    file_size = fields.Integer(string='File Size (Bytes)', readonly=True, copy=False)
    file_size_display = fields.Char(
        string='File Size',
        compute='_compute_file_size_display',
    )
    uploaded_by = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        readonly=True,
        ondelete='restrict',
        copy=False,
    )
    uploaded_at = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
        index=True,
    )

    @api.depends('file_size')
    def _compute_file_size_display(self):
        units = (_('bytes'), _('KB'), _('MB'), _('GB'))
        for material in self:
            size = float(material.file_size or 0)
            unit = units[0]
            for unit in units:
                if size < 1024 or unit == units[-1]:
                    break
                size /= 1024
            material.file_size_display = (
                '%d %s' % (size, unit)
                if unit == units[0]
                else '%.1f %s' % (size, unit)
            )

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group('ab_training_tasks.group_training_tasks_manager')
        prepared_vals = []
        for incoming in vals_list:
            vals = dict(incoming)
            task = self.env['ab.training.task'].browse(vals.get('task_id')).exists()
            if not task:
                raise ValidationError(_('A valid training task is required.'))
            if not is_manager:
                if task.member_id != self.env.user:
                    raise AccessError(_('Members can only upload files to their own training tasks.'))
                if task.state not in ('pending', 'rejected'):
                    raise AccessError(_('Files can only be uploaded before a task is approved.'))

            file_name = self._sanitize_file_name(vals.get('file_name'))
            content = self._decode_file(vals.get('file_data'))
            file_type, detected_mimetype = self._classify_file(content, file_name)
            if not file_type:
                raise ValidationError(_(
                    'Unsupported file type. Upload an image, PDF, PowerPoint, video, or audio file.'
                ))
            if not task.category_id._allows_file_type(file_type):
                file_type_label = task.category_id._file_type_label(file_type)
                raise ValidationError(_(
                    'The selected material category does not allow %s files.'
                ) % file_type_label)

            vals.update({
                'file_name': file_name,
                'accepted_file_extensions': task.category_id._allowed_file_extensions(),
                'file_type': file_type,
                'mimetype': detected_mimetype,
                'file_size': len(content),
                'uploaded_by': self.env.user.id,
                'uploaded_at': fields.Datetime.now(),
            })
            prepared_vals.append(vals)
        return super().create(prepared_vals)

    def unlink(self):
        if not self.env.user.has_group('ab_training_tasks.group_training_tasks_manager'):
            raise AccessError(_('Only training managers can delete training materials.'))
        return super().unlink()

    @api.model
    def _sanitize_file_name(self, file_name):
        sanitized = (file_name or '').strip().replace('\\', '/').rsplit('/', 1)[-1]
        if not sanitized or '\x00' in sanitized:
            raise ValidationError(_('A valid file name is required.'))
        return sanitized

    @api.model
    def _decode_file(self, file_data):
        if not file_data:
            raise ValidationError(_('Select a file to upload.'))
        try:
            encoded = file_data.encode() if isinstance(file_data, str) else file_data
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, TypeError, ValueError):
            raise ValidationError(_('The uploaded file could not be read.')) from None
        if not content:
            raise ValidationError(_('Empty files cannot be uploaded.'))
        return content

    @api.model
    def _classify_file(self, content, file_name):
        detected = (guess_mimetype(content, default='application/octet-stream') or '').lower()
        detected = detected.split(';', 1)[0]
        extension = os.path.splitext(file_name.lower())[1]
        extension_mimetype = (mimetypes.guess_type(file_name)[0] or '').lower()

        if detected.startswith('image/'):
            return 'image', detected
        if detected == 'application/pdf':
            return 'pdf', detected
        if detected in POWERPOINT_MIMETYPES:
            return 'ppt', detected
        if (
            extension in POWERPOINT_ARCHIVE_EXTENSIONS
            and detected in POWERPOINT_ARCHIVE_MIMETYPES
            and self._is_powerpoint_archive(content)
        ):
            return 'ppt', extension_mimetype or detected
        if extension in POWERPOINT_LEGACY_EXTENSIONS and detected in POWERPOINT_LEGACY_MIMETYPES:
            return 'ppt', extension_mimetype or detected
        if detected.startswith('video/'):
            return 'video', detected
        if detected.startswith('audio/'):
            return 'audio', detected

        if detected == 'application/octet-stream':
            if extension_mimetype.startswith('image/'):
                return 'image', extension_mimetype
            if extension_mimetype.startswith('video/'):
                return 'video', extension_mimetype
            if extension_mimetype.startswith('audio/'):
                return 'audio', extension_mimetype
        return False, detected

    @api.model
    def _is_powerpoint_archive(self, content):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
        except (OSError, zipfile.BadZipFile):
            return False
        return '[Content_Types].xml' in names and any(name.startswith('ppt/') for name in names)
