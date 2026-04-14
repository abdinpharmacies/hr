from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbdinInterviews(models.Model):
    _name = "ab_hr_interview"
    _description = "Abdin HR Interviews"

    applicant_id = fields.Many2one('ab_hr_application', required=True)
    interviewer_id = fields.Many2one('ab_hr_employee', required=True)
    interview_date = fields.Datetime(required=True)
    active = fields.Boolean(default=True)
    required_job_id = fields.Many2one(
        'ab_required_job',
        related='applicant_id.required_job_id',
        string="Required Job",
    )
    type_of_form = fields.Selection(related='applicant_id.type_of_form', string="Type of Form")

    action = fields.Selection(
        selection=[('accepted_job_offer', 'Accepted-Job Offer'),
                   ('accepted_short_list', 'Accepted-Short List'),
                   ('accepted_waiting_list', 'Accepted-Waiting List'),
                   ('training', 'Training'),
                   ('s_list', 'S.List'),
                   ('rejected', 'Rejected'),
                   ('archived', 'Archived'),
                   ('advanced_training', 'Advanced Training'),
                   ('duplicated_training', 'Duplicated Training'),
                   ('re_appraisal_interview', 'Re-Appraisal Interview')]
    )

    store_id = fields.Many2one('ab_store')
    starting_date = fields.Date()
    ending_date = fields.Date()
    from_hour = fields.Float()
    to_hour = fields.Float()

    # _sql_constraints = [
    #     ('unique_Interview', 'unique (applicant_id,interview_date)', 'Interview must be unique!'),
    # ]

    def _reset_training_fields(self):
        self.store_id = False
        self.starting_date = False
        self.ending_date = False
        self.from_hour = 0.0
        self.to_hour = 0.0

    @api.onchange('interview_date', 'action')
    def _onchange_interview_date(self):
        for rec in self:
            if not rec.interview_date:
                continue

            now = fields.Datetime.now()

            if rec.interview_date > now:
                rec._reset_training_fields()
                if rec.action:
                    rec.action = False
                    return {
                        'warning': {
                            'title': _("Invalid Action"),
                            'message': _("You cannot set an interview result before the interview date."),
                        }
                    }

            if rec.action == 'accepted_job_offer':
                rec._reset_training_fields()

            if rec.action in ('accepted_short_list', 'accepted_waiting_list', 'rejected',
                              'archived', 'advanced_training', 're_appraisal_interview'):
                rec._reset_training_fields()

    def action_interview_result_wizard(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Register Result"),
            "res_model": "ab_hr_interview_result_wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_interview_id": self.id,
                "default_applicant_id": self.applicant_id.id,
                "default_interviewer_id": self.interviewer_id.id,
            },
        }
