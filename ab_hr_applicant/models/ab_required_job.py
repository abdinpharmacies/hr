from odoo import api, fields, models


class AbRequiredJob(models.Model):
    _name = "ab_required_job"
    _description = "Required Job"
    _order = "name, id"

    _unique_required_job = models.Constraint(
        "UNIQUE(job_id)",
        "Each HR Job can only be linked once in Required Jobs.",
    )

    name = fields.Char(required=True)
    job_id = fields.Many2one("ab_hr_job", required=True, ondelete="restrict", index=True)
    is_publish = fields.Boolean(default=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("job_id") and not vals.get("name"):
                vals["name"] = self.env["ab_hr_job"].browse(vals["job_id"]).name
        return super().create(vals_list)

    def init(self):
        # Keep required jobs in sync with legacy ab_hr_job for missing entries.
        self.env.cr.execute(
            """
            INSERT INTO ab_required_job
                (name, job_id, is_publish, create_uid, create_date, write_uid, write_date)
            SELECT
                j.name, j.id, TRUE, 1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
            FROM ab_hr_job j
            LEFT JOIN ab_required_job r ON r.job_id = j.id
            WHERE r.id IS NULL
            """
        )
