from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbHrInterviewResultWizard(models.TransientModel):
    _name = "ab_hr_interview_result_wizard"
    _description = "Interview Result Wizard"

    interview_id = fields.Many2one("ab_hr_interview", string="Interview", required=True, readonly=True)
    applicant_id = fields.Many2one(related="interview_id.applicant_id", readonly=True)
    interviewer_id = fields.Many2one(related="interview_id.interviewer_id", readonly=True)
    interview_date = fields.Datetime(related="interview_id.interview_date", readonly=True)
    action = fields.Selection(
        selection=[
            ('accepted_job_offer', 'Accepted-Job Offer'),
            ('accepted_short_list', 'Accepted-Short List'),
            ('accepted_waiting_list', 'Accepted-Waiting List'),
            ('training', 'Training'),
            ('s_list', 'S.List'),
            ('rejected', 'Rejected'),
            ('archived', 'Archived'),
            ('advanced_training', 'Advanced Training'),
            ('duplicated_training', 'Duplicated Training'),
            ('re_appraisal_interview', 'Re-Appraisal Interview'),
        ],
        required=True,
        string="Result",
    )
    store_id = fields.Many2one('ab_store', string="Store")
    starting_date = fields.Date(string="Start Date")
    ending_date = fields.Date(string="End Date")
    from_hour = fields.Float(string="From", help="Float time, e.g. 8.5 = 08:30")
    to_hour = fields.Float(string="To", help="Float time, e.g. 17.0 = 17:00")

    note = fields.Text(string="Notes")

    def _is_training_action(self, action):
        return action in ('training', 'advanced_training', 'duplicated_training', 're_appraisal_interview')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "ab_hr_interview" and active_id:
            res["interview_id"] = active_id
            interview = self.env["ab_hr_interview"].browse(active_id)
            res.update({
                "action": interview.action or False,
                "store_id": interview.store_id.id if interview.store_id else False,
                "starting_date": interview.starting_date,
                "ending_date": interview.ending_date,
                "from_hour": interview.from_hour,
                "to_hour": interview.to_hour,
            })
        return res

    @api.constrains("action", "starting_date", "ending_date", "from_hour", "to_hour")
    def _check_training_fields(self):
        for wiz in self:
            if not wiz.action:
                continue
            if wiz._is_training_action(wiz.action):
                if not wiz.store_id:
                    raise ValidationError(_("Store is required for Training actions."))
                if not wiz.starting_date or not wiz.ending_date:
                    raise ValidationError(_("Start Date and End Date are required for Training actions."))
                if wiz.ending_date < wiz.starting_date:
                    raise ValidationError(_("End Date must be after Start Date."))
                if wiz.from_hour and wiz.to_hour and wiz.to_hour <= wiz.from_hour:
                    raise ValidationError(_("To hour must be greater than From hour."))
            else:
                pass

    def action_confirm(self):
        self.ensure_one()
        interview = self.interview_id
        now = fields.Datetime.now()
        if interview.interview_date and interview.interview_date > now:
            raise ValidationError(_("You cannot set an interview result before the interview date."))
        vals = {"action": self.action}
        if self._is_training_action(self.action):
            vals.update({
                "store_id": self.store_id.id,
                "starting_date": self.starting_date,
                "ending_date": self.ending_date,
                "from_hour": self.from_hour or 0.0,
                "to_hour": self.to_hour or 0.0,
            })
        else:
            vals.update({
                "store_id": False,
                "starting_date": False,
                "ending_date": False,
                "from_hour": 0.0,
                "to_hour": 0.0,
            })

        interview.write(vals)
        return {"type": "ir.actions.act_window_close"}
