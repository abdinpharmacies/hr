from odoo import api, fields, models


class AbPharmacyDeliveryBranch(models.Model):
    _name = "ab_pharmacy_delivery_branch"
    _description = "Pharmacy Delivery Branch"
    _order = "name, id"
    _rec_name = "name"

    _uniq_branch_name = models.Constraint(
        "UNIQUE(name)",
        "Branch name must be unique.",
    )

    name = fields.Char(required=True, index=True)
    hr_department_id = fields.Many2one(
        "ab_hr_department",
        string="HR Department",
        ondelete="set null",
        index=True,
    )
    user_ids = fields.Many2many(
        "res.users",
        "ab_pharmacy_delivery_branch_user_rel",
        "branch_id",
        "user_id",
        string="Allowed Users",
        help="Users allowed to see this branch and its related delivery records.",
    )
    pilot_ids = fields.One2many(
        "ab_pharmacy_delivery_pilot",
        "branch_id",
        string="Pilots",
    )
    related_branch_ids = fields.Many2many(
        "ab_pharmacy_delivery_branch",
        compute="_compute_related_branch_ids",
        string="Branches",
    )
    assignment_ids = fields.One2many(
        "ab_pharmacy_delivery_assignment",
        "branch_id",
        string="Assignments",
    )
    pilot_count = fields.Integer(compute="_compute_branch_counts")
    assignment_count = fields.Integer(compute="_compute_branch_counts")

    _uniq_hr_department = models.Constraint(
        "UNIQUE(hr_department_id)",
        "Each HR department can be linked to only one branch.",
    )

    def _compute_branch_counts(self):
        grouped = self.env["ab_pharmacy_delivery_pilot"].read_group(
            [("branch_id", "in", self.ids)],
            ["branch_id"],
            ["branch_id"],
        )
        pilot_counts = {
            row["branch_id"][0]: row.get("__count", row.get("branch_id_count", 0))
            for row in grouped
            if row.get("branch_id")
        }
        grouped_assignments = self.env["ab_pharmacy_delivery_assignment"].read_group(
            [("branch_id", "in", self.ids)],
            ["branch_id"],
            ["branch_id"],
        )
        assignment_counts = {
            row["branch_id"][0]: row.get("__count", row.get("branch_id_count", 0))
            for row in grouped_assignments
            if row.get("branch_id")
        }
        for branch in self:
            branch.pilot_count = pilot_counts.get(branch.id, 0)
            branch.assignment_count = assignment_counts.get(branch.id, 0)

    def _compute_related_branch_ids(self):
        branches = self.search([], order="name, id")
        for branch in self:
            branch.related_branch_ids = branches

    @api.model
    def _get_or_create_from_department(self, department):
        branch = self.search([("hr_department_id", "=", department.id)], limit=1)
        if branch:
            if branch.name != department.name:
                branch.name = department.name
            return branch
        return self.create(
            {
                "name": department.name,
                "hr_department_id": department.id,
            }
        )
