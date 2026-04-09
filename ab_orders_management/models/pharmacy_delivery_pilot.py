from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PILOT_STATUS_LABELS = dict(
    [
        ("free", "Available"),
        ("in_delivery", "In Delivery"),
    ]
)


class AbPharmacyDeliveryPilot(models.Model):
    _name = "ab_pharmacy_delivery_pilot"
    _description = "Pharmacy Delivery Pilot"
    _order = "status, name, id"
    _rec_name = "name"

    _uniq_pilot_name_branch = models.Constraint(
        "UNIQUE(name, branch_id)",
        "Pilot name must be unique per branch.",
    )
    _uniq_pilot_hr_employee = models.Constraint(
        "UNIQUE(hr_employee_id)",
        "Each HR employee can be linked to only one pilot.",
    )

    name = fields.Char(required=True, index=True)
    pilot_code = fields.Char(string="Pilot Code", index=True)
    shift = fields.Char(string="Shift", index=True)
    sign_in_datetime = fields.Datetime(string="Sign In Date & Time", index=True)
    sign_in_date = fields.Date(compute="_compute_sign_in_fields", store=True, index=True)
    sign_in_order = fields.Integer(string="Pilot Order", compute="_compute_sign_in_fields")
    daily_handle_count = fields.Integer(
        string="Daily Orders/Deliveries Count",
        compute="_compute_daily_handle_count",
    )
    hr_employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Employee",
        ondelete="restrict",
        index=True,
    )
    branch_id = fields.Many2one(
        "ab_pharmacy_delivery_branch",
        required=True,
        ondelete="restrict",
        index=True,
    )
    status = fields.Selection(
        [
            ("free", _("Available")),
            ("in_delivery", _("In Delivery")),
        ],
        default="free",
        required=True,
        index=True,
    )
    assignment_ids = fields.One2many(
        "ab_pharmacy_delivery_assignment",
        "pilot_id",
        string="Assignments",
    )
    hr_job_id = fields.Many2one(
        "ab_hr_job",
        related="hr_employee_id.job_id",
        store=True,
        readonly=True,
    )
    hr_department_id = fields.Many2one(
        "ab_hr_department",
        related="hr_employee_id.department_id",
        store=True,
        readonly=True,
    )
    hr_parent_department_id = fields.Many2one(
        "ab_hr_department",
        related="hr_employee_id.parent_department_id",
        store=True,
        readonly=True,
    )
    delivery_assigned_count = fields.Integer(
        compute="_compute_handle_counts",
        store=True,
    )
    delivery_completed_count = fields.Integer(
        compute="_compute_handle_counts",
        store=True,
    )
    order_assigned_count = fields.Integer(
        compute="_compute_handle_counts",
        store=True,
    )
    order_completed_count = fields.Integer(
        compute="_compute_handle_counts",
        store=True,
    )
    handled_item_count = fields.Integer(
        compute="_compute_handle_counts",
        store=True,
    )

    @api.depends("assignment_ids.status", "assignment_ids.transaction_type")
    def _compute_handle_counts(self):
        for pilot in self:
            pilot.delivery_assigned_count = 0
            pilot.delivery_completed_count = 0
            pilot.order_assigned_count = 0
            pilot.order_completed_count = 0
            pilot.handled_item_count = 0

        if not self:
            return

        grouped = self.env["ab_pharmacy_delivery_assignment"].read_group(
            [("pilot_id", "in", self.ids)],
            ["pilot_id", "transaction_type", "status"],
            ["pilot_id", "transaction_type", "status"],
            lazy=False,
        )
        counts = {
            pilot.id: {
                "delivery_assigned_count": 0,
                "delivery_completed_count": 0,
                "order_assigned_count": 0,
                "order_completed_count": 0,
            }
            for pilot in self
        }
        for row in grouped:
            pilot_value = row.get("pilot_id")
            if not pilot_value:
                continue
            pilot_id = pilot_value[0]
            amount = row.get("__count", row.get("pilot_id_count", 0)) or 0
            transaction_type = row.get("transaction_type")
            status = row.get("status")
            bucket = counts.setdefault(
                pilot_id,
                {
                    "delivery_assigned_count": 0,
                    "delivery_completed_count": 0,
                    "order_assigned_count": 0,
                    "order_completed_count": 0,
                },
            )
            if transaction_type == "delivery" and status == "assigned":
                bucket["delivery_assigned_count"] += amount
            elif transaction_type == "delivery" and status == "done":
                bucket["delivery_completed_count"] += amount
            elif transaction_type == "order" and status == "assigned":
                bucket["order_assigned_count"] += amount
            elif transaction_type == "order" and status == "done":
                bucket["order_completed_count"] += amount

        for pilot in self:
            bucket = counts.get(pilot.id, {})
            pilot.delivery_assigned_count = bucket.get("delivery_assigned_count", 0)
            pilot.delivery_completed_count = bucket.get("delivery_completed_count", 0)
            pilot.order_assigned_count = bucket.get("order_assigned_count", 0)
            pilot.order_completed_count = bucket.get("order_completed_count", 0)
            pilot.handled_item_count = pilot.delivery_completed_count + pilot.order_completed_count

    @api.depends("sign_in_datetime", "branch_id")
    def _compute_sign_in_fields(self):
        for pilot in self:
            pilot.sign_in_date = fields.Date.to_date(pilot.sign_in_datetime) if pilot.sign_in_datetime else False
            pilot.sign_in_order = 0

        grouped = {}
        for pilot in self.filtered(lambda item: item.sign_in_datetime and item.branch_id):
            grouped[(pilot.branch_id.id, pilot.sign_in_date)] = True

        for branch_id, sign_in_date in grouped:
            start = datetime.combine(sign_in_date, time.min)
            end = datetime.combine(sign_in_date, time.max)
            ordered = self.search(
                [
                    ("branch_id", "=", branch_id),
                    ("sign_in_datetime", ">=", fields.Datetime.to_string(start)),
                    ("sign_in_datetime", "<=", fields.Datetime.to_string(end)),
                ],
                order="sign_in_datetime, id",
            )
            for index, pilot in enumerate(ordered, start=1):
                pilot.sign_in_order = index

    @api.depends("assignment_ids.start_datetime", "sign_in_datetime")
    def _compute_daily_handle_count(self):
        Assignment = self.env["ab_pharmacy_delivery_assignment"]
        for pilot in self:
            pivot_date = pilot.sign_in_date or fields.Date.context_today(pilot)
            start = datetime.combine(pivot_date, time.min)
            end = datetime.combine(pivot_date, time.max)
            pilot.daily_handle_count = Assignment.search_count(
                [
                    ("pilot_id", "=", pilot.id),
                    ("start_datetime", ">=", fields.Datetime.to_string(start)),
                    ("start_datetime", "<=", fields.Datetime.to_string(end)),
                    ("status", "!=", "cancelled"),
                ]
            )

    def _get_open_assignment(self):
        self.ensure_one()
        return self.env["ab_pharmacy_delivery_assignment"].search(
            [("pilot_id", "=", self.id), ("status", "=", "assigned")],
            order="start_datetime desc, id desc",
            limit=1,
        )

    def _sync_status_from_assignments(self):
        pilots = self.filtered(lambda pilot: pilot.exists())
        if not pilots:
            return
        open_assignment_pilot_ids = set(
            self.env["ab_pharmacy_delivery_assignment"].search(
                [("pilot_id", "in", pilots.ids), ("status", "=", "assigned")],
                order="start_datetime desc, id desc",
            ).mapped("pilot_id").ids
        )
        for pilot in pilots:
            desired_status = "in_delivery" if pilot.id in open_assignment_pilot_ids else "free"
            if pilot.status != desired_status:
                pilot.status = desired_status

    @api.model
    def _get_translated_selection_label(self, model_name, field_name, value):
        if not value:
            return value
        field_info = self.env[model_name].fields_get([field_name]).get(field_name, {})
        selection = dict(field_info.get("selection", []))
        return selection.get(value, value)

    @api.model
    def _get_target_departments(self):
        Department = self.env["ab_hr_department"]
        return Department.search(
            [
                "|",
                ("name", "ilike", "الاقصر"),
                ("parent_id.name", "ilike", "الاقصر"),
            ],
            order="name, id",
        )

    @api.model
    def _get_hr_delivery_employee_domain(self, department_id=False):
        domain = [
            ("job_id", "!=", False),
            ("job_id.name", "ilike", "مندوب توصيل"),
            ("department_id", "!=", False),
            "|",
            ("department_id.name", "ilike", "الاقصر"),
            ("parent_department_id.name", "ilike", "الاقصر"),
        ]
        if department_id:
            domain = [("department_id", "=", department_id)] + domain
        return domain

    @api.model
    def action_sync_pilots_from_hr(self, department_id=False):
        Employee = self.env["ab_hr_employee"].sudo()
        Branch = self.env["ab_pharmacy_delivery_branch"]
        employees = Employee.search(self._get_hr_delivery_employee_domain(department_id=department_id))
        created_count = 0
        updated_count = 0
        for employee in employees:
            department = employee.department_id
            if not department:
                continue
            branch = Branch._get_or_create_from_department(department)
            pilot = self.search([("hr_employee_id", "=", employee.id)], limit=1)
            vals = {
                "branch_id": branch.id,
            }
            if pilot:
                if not pilot.name:
                    vals["name"] = employee.name
                pilot.write(vals)
                updated_count += 1
            else:
                vals["hr_employee_id"] = employee.id
                vals["name"] = employee.name
                vals["status"] = "free"
                self.create(vals)
                created_count += 1
        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "total_count": len(employees),
        }

    def _prepare_status_wizard_action(self):
        self.ensure_one()
        wizard_view = self.env.ref(
            "ab_orders_management.view_ab_pharmacy_delivery_assignment_wizard_form",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Change Pilot Status"),
            "res_model": "ab_pharmacy_delivery_assignment_wizard",
            "view_mode": "form",
            "views": [(wizard_view.id, "form")] if wizard_view else [(False, "form")],
            "target": "new",
            "context": {
                "default_pilot_id": self.id,
                "default_target_status": "free" if self.status == "in_delivery" else "in_delivery",
                "default_branch_id": self.branch_id.id,
            },
        }

    def action_open_status_wizard(self):
        self.ensure_one()
        return self._prepare_status_wizard_action()

    @api.model
    def action_open_status_wizard_from_dashboard(self, pilot_id):
        pilot = self.browse(pilot_id)
        pilot.ensure_one()
        return pilot._prepare_status_wizard_action()

    def action_start_delivery(self, order_number, transaction_type, branch_id, note=False):
        self.ensure_one()
        if self.status == "in_delivery":
            raise UserError(_("The pilot is already in delivery."))
        if not order_number:
            raise UserError(_("Order number is required."))
        assignment = self.env["ab_pharmacy_delivery_assignment"].create(
            {
                "pilot_id": self.id,
                "branch_id": branch_id or self.branch_id.id,
                "order_number": order_number,
                "transaction_type": transaction_type,
                "status": "assigned",
                "start_datetime": fields.Datetime.now(),
                "note": note or "",
            }
        )
        self.status = "in_delivery"
        return assignment

    def action_finish_delivery(self, note=False):
        self.ensure_one()
        assignment = self._get_open_assignment()
        if not assignment:
            # Allow managers to recover inconsistent status states without blocking UI flow.
            self.status = "free"
            return False
        assignment.action_mark_done(note=note)
        self.status = "free"
        return assignment

    @api.model
    def get_dashboard_payload(self, branch_id=False, department_id=False):
        Branch = self.env["ab_pharmacy_delivery_branch"]
        Pilot = self.env["ab_pharmacy_delivery_pilot"]
        Assignment = self.env["ab_pharmacy_delivery_assignment"]
        departments = self._get_target_departments()
        target_department_ids = set(departments.ids)
        selected_department_id = int(department_id or 0)
        if selected_department_id and selected_department_id not in target_department_ids:
            selected_department_id = 0

        sync_result = self.action_sync_pilots_from_hr(
            department_id=selected_department_id or False
        )

        branches = Branch.search([], order="name, id")
        selected_branch_id = int(branch_id or 0)
        selected_branch = Branch.browse(selected_branch_id) if selected_branch_id else Branch.browse()
        if selected_branch_id and not selected_branch.exists():
            selected_branch_id = 0
            selected_branch = Branch.browse()

        base_domain = [("branch_id", "=", selected_branch_id)] if selected_branch_id else []
        department_count_rows = Pilot.read_group(
            base_domain + [("hr_department_id", "!=", False)],
            ["hr_department_id"],
            ["hr_department_id"],
            lazy=False,
        )
        department_count_map = {
            row["hr_department_id"][0]: row.get("__count", row.get("hr_department_id_count", 0))
            for row in department_count_rows
            if row.get("hr_department_id")
        }

        domain = list(base_domain)
        if selected_department_id:
            domain.append(("hr_department_id", "=", selected_department_id))
        pilots = Pilot.search(domain, order="status, name, id")
        open_assignments = Assignment.search(
            [("pilot_id", "in", pilots.ids), ("status", "=", "assigned")],
            order="start_datetime desc, id desc",
        )
        open_assignment_map = {}
        for assignment in open_assignments:
            if assignment.pilot_id.id not in open_assignment_map:
                open_assignment_map[assignment.pilot_id.id] = assignment

        branch_payload = [
            {
                "id": branch.id,
                "name": branch.name,
                "pilot_count": branch.pilot_count,
                "assignment_count": branch.assignment_count,
            }
            for branch in branches
        ]
        pilot_payload = []
        for pilot in pilots:
            open_assignment = open_assignment_map.get(pilot.id)
            status_label = self._get_translated_selection_label(
                "ab_pharmacy_delivery_pilot",
                "status",
                pilot.status,
            )
            pilot_payload.append(
                {
                    "id": pilot.id,
                    "name": pilot.name,
                    "pilot_code": pilot.pilot_code or "",
                    "shift": pilot.shift or "",
                    "sign_in_datetime": fields.Datetime.to_string(pilot.sign_in_datetime) if pilot.sign_in_datetime else False,
                    "sign_in_date": fields.Date.to_string(pilot.sign_in_date) if pilot.sign_in_date else False,
                    "sign_in_order": pilot.sign_in_order,
                    "daily_handle_count": pilot.daily_handle_count,
                    "status": pilot.status,
                    "status_label": status_label,
                    "hr_employee_id": pilot.hr_employee_id.id,
                    "branch_id": pilot.branch_id.id,
                    "branch_name": pilot.branch_id.name,
                    "department_id": pilot.hr_department_id.id,
                    "department_name": pilot.hr_department_id.name or "",
                    "delivery_assigned_count": pilot.delivery_assigned_count,
                    "delivery_completed_count": pilot.delivery_completed_count,
                    "order_assigned_count": pilot.order_assigned_count,
                    "order_completed_count": pilot.order_completed_count,
                    "handled_item_count": pilot.handled_item_count,
                    "current_assignment": {
                        "id": open_assignment.id,
                        "order_number": open_assignment.order_number,
                        "transaction_type": open_assignment.transaction_type,
                        "transaction_type_label": self._get_translated_selection_label(
                            "ab_pharmacy_delivery_assignment",
                            "transaction_type",
                            open_assignment.transaction_type,
                        ),
                        "branch_name": open_assignment.branch_id.name,
                        "start_datetime": fields.Datetime.to_string(open_assignment.start_datetime),
                        "note": open_assignment.note or "",
                    }
                    if open_assignment
                    else False,
                }
            )

        return {
            "branches": branch_payload,
            "selected_branch_id": selected_branch_id or 0,
            "selected_branch_name": selected_branch.name if selected_branch else "",
            "departments": [
                {
                    "id": department.id,
                    "name": department.name,
                    "pilot_count": department_count_map.get(department.id, 0),
                }
                for department in departments
            ],
            "selected_department_id": selected_department_id,
            "pilots": pilot_payload,
            "available_pilots": sorted(
                [
                    pilot
                    for pilot in pilot_payload
                    if pilot["status"] == "free" and pilot["sign_in_datetime"]
                ]
                or [pilot for pilot in pilot_payload if pilot["status"] == "free"],
                key=lambda x: (x["sign_in_order"] or 999999, x["name"]),
            ),
            "in_delivery_pilots": sorted(
                [
                    pilot
                    for pilot in pilot_payload
                    if pilot["status"] == "in_delivery" and pilot["sign_in_datetime"]
                ]
                or [pilot for pilot in pilot_payload if pilot["status"] == "in_delivery"],
                key=lambda x: (x["sign_in_order"] or 999999, x["name"]),
            ),
            "totals": {
                "pilot_count": len(pilot_payload),
                "available_count": len([pilot for pilot in pilot_payload if pilot["status"] == "free"]),
                "in_delivery_count": len([pilot for pilot in pilot_payload if pilot["status"] == "in_delivery"]),
                "delivery_completed_count": sum(pilot["delivery_completed_count"] for pilot in pilot_payload),
                "order_completed_count": sum(pilot["order_completed_count"] for pilot in pilot_payload),
                "handled_item_count": sum(pilot["handled_item_count"] for pilot in pilot_payload),
            },
            "sync": sync_result,
        }
