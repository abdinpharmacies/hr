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
    announcement_link = fields.Char(compute='_compute_announcement_link', compute_sudo=True, store=False)

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
        for rec in self:
            # Get the human-readable label for announcement_type
            announcement_type_label = dict(rec._fields['announcement_type'].selection).get(rec.announcement_type, rec.announcement_type)
            
            if rec.title == 'decree' and rec.number:
                rec.display_name = f"{announcement_type_label} ({rec.number})"
            else:
                rec.display_name = announcement_type_label

    def _compute_announcement_link(self):
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if base_url:
                # Ensure the base_url doesn't end with a slash to avoid double slashes
                base_url = base_url.rstrip('/')
                rec.announcement_link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"
            else:
                rec.announcement_link = False

    def _get_default_subject_body(self):
        # Provide a more flexible default template
        return """
        <div style="font-family: Arial, sans-serif;">
            <h1 style="text-align: center; color: #2c3e50;">Announcement Title</h1>
            <div style="line-height: 1.6;">
                <p>Enter your announcement content here...</p>
                <p>You can use this space to provide detailed information, instructions, or updates.</p>
            </div>
            <hr style="border: 1px solid #eee; margin: 20px 0;">
            <footer style="font-size: 0.9em; color: #7f8c8d;">
                <p>Issued by: [Department Name]</p>
                <p>Release Date: [Date]</p>
            </footer>
        </div>
        """
