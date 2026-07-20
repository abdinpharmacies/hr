from odoo import fields, models, _


TRAINING_FILE_TYPES = [
    ('image', 'Images'),
    ('pdf', 'PDF'),
    ('ppt', 'PowerPoint'),
    ('video', 'Videos'),
    ('audio', 'Audio'),
]

TRAINING_FILE_TYPE_FIELDS = {
    'image': 'allow_image_files',
    'pdf': 'allow_pdf_files',
    'ppt': 'allow_ppt_files',
    'video': 'allow_video_files',
    'audio': 'allow_audio_files',
}

TRAINING_FILE_TYPE_ACCEPTS = {
    'image': 'image/*',
    'pdf': '.pdf',
    'ppt': '.ppt,.pptx,.pps,.ppsx,.pot,.potx,.pptm,.ppsm,.potm',
    'video': 'video/*',
    'audio': 'audio/*',
}


class TrainingTaskCategory(models.Model):
    _name = 'ab.training.task.category'
    _description = 'Training Task Category'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    task_type_ids = fields.One2many(
        'ab.training.task.type',
        'category_id',
        string='Task Types',
    )
    allow_image_files = fields.Boolean(string='Images')
    allow_pdf_files = fields.Boolean(string='PDF')
    allow_ppt_files = fields.Boolean(string='PowerPoint')
    allow_video_files = fields.Boolean(string='Videos')
    allow_audio_files = fields.Boolean(string='Audio')

    def _allows_file_type(self, file_type):
        self.ensure_one()
        field_name = TRAINING_FILE_TYPE_FIELDS.get(file_type)
        return bool(field_name and self[field_name])

    def _file_type_label(self, file_type):
        self.ensure_one()
        labels = {
            'image': _('Images'),
            'pdf': _('PDF'),
            'ppt': _('PowerPoint'),
            'video': _('Videos'),
            'audio': _('Audio'),
        }
        return labels.get(file_type, file_type)

    def _allowed_file_type_labels(self):
        self.ensure_one()
        return [
            self._file_type_label(file_type)
            for file_type, _label in TRAINING_FILE_TYPES
            if self._allows_file_type(file_type)
        ]

    def _allowed_file_extensions(self):
        self.ensure_one()
        return ','.join(
            TRAINING_FILE_TYPE_ACCEPTS[file_type]
            for file_type, _label in TRAINING_FILE_TYPES
            if self._allows_file_type(file_type)
        )
