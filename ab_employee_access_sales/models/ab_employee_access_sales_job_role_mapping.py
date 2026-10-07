from odoo import fields, models


class AbEmployeeAccessSalesJobRoleMapping(models.Model):
    _name = "ab_employee_access_sales_job_role_mapping"
    _description = "Employee Sales Job Role Mapping"
    _rec_name = "job_id"
    _order = "job_id, id"

    job_id = fields.Many2one(
        "ab_hr_job", string="Job", required=True, ondelete="restrict",
        domain=[("active", "=", True)],
    )
    role_id = fields.Many2one(
        "ab_employee_access_sales_role", string="Sales Role", required=True,
        ondelete="restrict", domain=[("active", "=", True)],
    )

    _job_unique = models.Constraint("UNIQUE(job_id)", "Each job can only have one sales role mapping.")
