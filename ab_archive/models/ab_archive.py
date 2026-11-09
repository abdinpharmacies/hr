import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbArchive(models.Model):
    _name = 'ab_archive'
    _description = 'ab_archive'
    _order = 'id desc'

    name = fields.Char(string='Description', default='Notice')
    doc_code = fields.Char()
    att_file = fields.Binary(attachment=True)
    # Computed helpers so each widget only receives data it can display
    att_file_image = fields.Binary(compute='_compute_att_file_variants', store=False)
    att_file_pdf = fields.Binary(compute='_compute_att_file_variants', store=False)
    att_file_generic = fields.Binary(compute='_compute_att_file_variants', store=False)
    att_filename = fields.Char()
    att_is_image = fields.Boolean(compute='_compute_type', store=True)
    att_is_pdf = fields.Boolean(compute='_compute_type', store=True)
    doc_type = fields.Many2one('ab_archive_doc_type')
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id, store=True)
    archive_date = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True, copy=False)
    is_today = fields.Boolean(compute='_compute_is_today', search='_search_is_today')
    active = fields.Boolean(default=True)

    def btn_toggle_active(self):
        self.ensure_one()
        self.sudo().active = not self.active

    @api.depends('archive_date')
    def _compute_is_today(self):
        for rec in self:
            cutoff = fields.Datetime.now() - datetime.timedelta(hours=24)
            rec.is_today = bool(rec.archive_date and rec.archive_date >= cutoff)

    def _search_is_today(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        if operator != '=':  # that means it is '!='
            val = not val
        cutoff = fields.Datetime.now() - datetime.timedelta(hours=24)
        if val:
            return [('archive_date', '>=', cutoff)]
        return ['|', ('archive_date', '=', False), ('archive_date', '<', cutoff)]

    @api.depends('att_filename')
    def _compute_type(self):
        """Detect uploaded file type using file extension only."""
        image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'}
        for record in self:
            record.att_is_image = False
            record.att_is_pdf = False
            if record.att_filename:
                ext = record.att_filename.split('.')[-1].lower() if '.' in record.att_filename else ''
                if ext == 'pdf':
                    record.att_is_pdf = True
                elif ext in image_exts:
                    record.att_is_image = True

    @api.depends('att_file', 'att_is_image', 'att_is_pdf')
    def _compute_att_file_variants(self):
        """Expose the main binary to the matching widget only."""
        for rec in self:
            rec.att_file_image = rec.att_file if rec.att_is_image else False
            rec.att_file_pdf = rec.att_file if rec.att_is_pdf else False
            rec.att_file_generic = rec.att_file if not (rec.att_is_image or rec.att_is_pdf) else False


class AbArchiveDocType(models.Model):
    _name = 'ab_archive_doc_type'
    _description = 'ab_archive_doc_type'

    name = fields.Char()
