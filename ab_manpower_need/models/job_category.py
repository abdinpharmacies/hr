from odoo import api, fields, models


class JobCategory(models.Model):
    _name = 'ab_hr_job_cat'
    _description = 'HR Job Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True, index=True)
    active = fields.Boolean(default=True)
    job_ids = fields.Many2many(
        comodel_name='ab_hr_job',
        relation='ab_hr_job_cat_job_rel',
        column1='category_id',
        column2='job_id',
        string='Jobs',
    )

    _unique_name = models.Constraint(
        'UNIQUE(name)',
        'The job category name must be unique.',
    )


class ManpowerHourNeed(models.Model):
    _inherit = 'ab_hr_manpower_hour_need'

    job_category_id = fields.Many2one(
        'ab_hr_job_cat',
        string='Job Category',
        index=True,
    )
    available_job_ids = fields.Many2many(
        'ab_hr_job',
        compute='_compute_available_job_ids',
        string='Available Jobs',
    )

    @api.depends('job_category_id', 'job_category_id.job_ids')
    def _compute_available_job_ids(self):
        for rec in self:
            rec.available_job_ids = rec.job_category_id.job_ids

    @api.onchange('job_category_id')
    def _onchange_job_category_id(self):
        for rec in self:
            if (
                rec.job_category_id
                and rec.job_title
                and rec.job_title not in rec.job_category_id.job_ids
            ):
                rec.job_title = False
