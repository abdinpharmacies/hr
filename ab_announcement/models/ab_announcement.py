from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbAnnouncement(models.Model):
    _name = 'ab_announcement'
    _description = 'ab_announcement'
    _inherit = ['mail.thread']
    _order = 'release_date desc'
    _rec_name = 'title'

    title = fields.Selection(
        selection=[('decree', 'Decree'),
                   ('notice', 'Notice'),
                   ],
        default='decree',
        required=True,
    )

    subject = fields.Text(required=True)
    subject_body = fields.Html(default=lambda self: self._get_default_subject_body())
    issuer = fields.Many2one('ab_hr_department', required=True)
    release_date = fields.Date(required=True, index=True)
    announcement_type = fields.Selection(
        selection=[('policies_and_instructions', 'Policies And Instructions'),
                   ("employees_movements", "Employees' Movements"),
                   ('notices_and_warnings', 'Notices And Warnings'),
                   ('holidays', 'Holidays')
                   ],
        default="policies_and_instructions",
        required=True,
    )
    announcement_link = fields.Char(compute='_compute_announcement_link', compute_sudo=True)

    number = fields.Char()
    attachment = fields.Binary()
    is_posted = fields.Boolean()
    send_attachment = fields.Boolean(default=True)

    @api.constrains('title', 'number', 'announcement_type')
    def _constrains_ab_announcement(self):
        for rec in self:
            if rec.title == 'decree' and not rec.number:
                raise ValidationError(_("A number is required for decree!"))
            if rec.title == 'decree' and rec.announcement_type == 'notices_and_warnings':
                raise ValidationError(_("Notices and warning is not a decree!"))
            if rec.title == 'notice' and rec.announcement_type != 'notices_and_warnings':
                raise ValidationError(_("Type must be notices and warnings."))

    @api.depends('announcement_type', 'number', 'title')
    def _compute_display_name(self):
        selection_labels = dict(self._fields['announcement_type']._description_selection(self.env))
        for rec in self:
            number = f"({rec.number})" if rec.title == 'decree' else ""
            announcement_type = selection_labels.get(rec.announcement_type, rec.announcement_type)
            rec.display_name = f"{announcement_type} {number}"

    def _compute_announcement_link(self):
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            # Use the current record id to build a stable record-specific link
            rec.announcement_link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"

    def _get_default_subject_body(self):
        return """<h1 class='text-center'>Title</h1>
        <p>Paragraph</p>
        <footer>
        <p>Footer</p>
        </footer>
        """
