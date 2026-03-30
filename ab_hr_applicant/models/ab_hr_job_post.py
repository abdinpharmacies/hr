from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AbHrJobPost(models.Model):
    _name = 'ab_hr_job_post'
    _description = 'Abdin HR Job Post'
    _order = 'status asc, registration_start desc, sequence asc, id desc'

    name = fields.Char(string='Title', compute='_compute_name', store=True)
    job_id = fields.Many2one('ab_required_job', string='Job', required=True, ondelete='restrict')
    city_id = fields.Many2one('ab_city', string='City')

    registration_start = fields.Datetime(string='Registration Start', required=True)
    registration_end = fields.Datetime(string='Registration End', required=True)

    status = fields.Selection([
        ('upcoming', 'Upcoming'),
        ('available', 'Available'),
        ('ended', 'Ended'),
    ], string='status', compute='_compute_status', store=True, index=True)

    website_published = fields.Boolean(string='Published on Website', default=True)
    description = fields.Html(string='Description')
    sequence = fields.Integer(default=10)

    @api.depends('job_id', 'city_id')
    def _compute_name(self):
        for rec in self:
            job_name = rec.job_id.name or 'Job'
            city_name = rec.city_id.name if rec.city_id else ''
            rec.name = f"{job_name} - {city_name}" if city_name else job_name

    @api.depends('registration_start', 'registration_end')
    def _compute_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.registration_start and now < rec.registration_start:
                rec.status = 'upcoming'
            elif rec.registration_end and now > rec.registration_end:
                rec.status = 'ended'
            else:
                rec.status = 'available'
