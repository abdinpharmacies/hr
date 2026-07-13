from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class InternalShipment(models.Model):
    _name = "ab_internal_shipment"
    _description = "Internal Shipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "shipment_date desc, id desc"

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type != "form" or not self._should_hide_chatter_for_current_user():
            return result

        arch = result.get("arch")
        if not arch:
            return result

        root = etree.fromstring(arch)
        for chatter in root.xpath("//chatter"):
            chatter.getparent().remove(chatter)
        result["arch"] = etree.tostring(root, encoding="unicode")
        return result

    @api.model
    def _should_hide_chatter_for_current_user(self):
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin_user and self.env.user == admin_user:
            return False
        return self.env.user.has_group(
            "ab_internal_shipment_tracking.group_ab_internal_shipment_warehouse_receipt"
        )

    name = fields.Char(
        string="Shipment Reference",
        required=True,
        copy=False,
        default="/",
        readonly=True,
        tracking=True,
    )
    shipment_date = fields.Date(
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    shipment_type = fields.Selection(
        [
            ("documents", "Documents"),
            ("devices", "Devices"),
            ("mixed", "Mixed"),
            ("other", "Other"),
        ],
        required=True,
        default="documents",
        tracking=True,
    )
    subject = fields.Char(required=True, tracking=True)
    description = fields.Text()
    notes = fields.Text(tracking=True)
    delivery_method = fields.Selection(
        [
            ("company_vehicle", "Internal Company Vehicle"),
            ("external_company", "External Shipping Company"),
            ("hand_delivery", "Hand Delivery"),
            ("other", "Other"),
        ],
        required=True,
        default="hand_delivery",
        tracking=True,
    )
    expected_delivery_date = fields.Date(tracking=True)
    is_delayed = fields.Boolean(compute="_compute_is_delayed", store=True)
    shipment_count = fields.Integer(
        string="Shipment Count",
        default=1,
        readonly=True,
        aggregator="sum",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("in_transit", "In Transit"),
            ("awaiting_warehouse_receipt", "Waiting Warehouse Receipt"),
            ("awaiting_receipt", "Awaiting Receipt"),
            ("received", "Confirmed"),
            ("closed", "Closed"),
        ],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )

    sender_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "Employee"), ("user", "User")],
        required=True,
        default=lambda self: self._get_current_user_sender_values()["sender_type"],
        tracking=True,
    )
    sender_store_id = fields.Many2one(
        "ab_store",
        string="Sender Branch",
        domain=[("store_type", "=", "branch")],
        default=lambda self: self._get_current_user_sender_values()["sender_store_id"],
        tracking=True,
    )
    sender_department_id = fields.Many2one(
        "ab_hr_department",
        string="Sender Department",
        tracking=True,
    )
    sender_employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Sender Employee",
        tracking=True,
    )
    sender_employee_selection_type = fields.Selection(
        [("all", "All"), ("specific", "Specific Employees")],
        string="Send to",
        default="all",
    )
    sender_selected_employee_ids = fields.Many2many(
        "ab_hr_employee",
        "ab_internal_shipment_sender_employee_selected_rel",
        "shipment_id",
        "employee_id",
        string="Selected Sender Employees",
    )
    sender_user_id = fields.Many2one(
        "res.users",
        compute="_compute_party_users",
        store=True,
        index=True,
    )
    sender_display = fields.Char(compute="_compute_party_displays", store=True)
    sender_managed_department_display = fields.Char(
        compute="_compute_sender_managed_department_display",
    )

    recipient_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "User")],
        required=True,
        default="department",
        tracking=True,
    )
    recipient_store_id = fields.Many2one(
        "ab_store",
        string="Recipient Branch",
        domain=[("store_type", "=", "branch")],
        tracking=True,
    )
    recipient_department_id = fields.Many2one(
        "ab_hr_department",
        string="Recipient Department",
        tracking=True,
    )
    recipient_employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Recipient Employee",
        tracking=True,
    )
    recipient_employee_selection_type = fields.Selection(
        [("all", "All"), ("specific", "Specific Employees")],
        string="Send to",
        default="all",
    )
    recipient_selected_employee_ids = fields.Many2many(
        "ab_hr_employee",
        "ab_internal_shipment_recipient_employee_selected_rel",
        "shipment_id",
        "employee_id",
        string="Selected Recipient Employees",
    )
    recipient_confirmation_employee_ids = fields.Many2many(
        "ab_hr_employee",
        compute="_compute_recipient_confirmation_employee_ids",
        string="Receipt Confirmation Employees",
    )
    recipient_user_id = fields.Many2one(
        "res.users",
        compute="_compute_party_users",
        store=True,
        index=True,
    )
    recipient_display = fields.Char(compute="_compute_party_displays", store=True)
    sender_route_user_ids = fields.Many2many(
        "res.users",
        "ab_internal_shipment_sender_route_user_rel",
        "shipment_id",
        "user_id",
        compute="_compute_route_users",
        store=True,
        string="Sender Route Users",
    )
    recipient_route_user_ids = fields.Many2many(
        "res.users",
        "ab_internal_shipment_recipient_route_user_rel",
        "shipment_id",
        "user_id",
        compute="_compute_route_users",
        store=True,
        string="Recipient Route Users",
    )
    warehouse_route_user_ids = fields.Many2many(
        "res.users",
        "ab_internal_shipment_warehouse_route_user_rel",
        "shipment_id",
        "user_id",
        compute="_compute_route_users",
        store=True,
        string="Warehouse Route Users",
    )
    receipt_route_user_ids = fields.Many2many(
        "res.users",
        "ab_internal_shipment_receipt_route_user_rel",
        "shipment_id",
        "user_id",
        compute="_compute_route_users",
        store=True,
        string="Receipt Route Users",
    )
    can_current_user_receive = fields.Boolean(
        compute="_compute_can_current_user_receive",
    )
    can_current_user_manage_workflow = fields.Boolean(
        compute="_compute_current_user_action_permissions",
    )
    can_current_user_close = fields.Boolean(
        compute="_compute_current_user_action_permissions",
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    sent_by_id = fields.Many2one("res.users", readonly=True, index=True)
    sent_date = fields.Datetime(readonly=True)
    delivered_by_id = fields.Many2one("res.users", readonly=True, index=True)
    delivered_date = fields.Datetime(readonly=True)
    received_by_id = fields.Many2one("res.users", readonly=True, index=True)
    received_date = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True, index=True)
    closed_date = fields.Datetime(readonly=True)

    current_holder_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "Employee"), ("user", "User")],
        readonly=True,
        tracking=True,
    )
    current_holder_store_id = fields.Many2one("ab_store", readonly=True, tracking=True)
    current_holder_department_id = fields.Many2one("ab_hr_department", readonly=True, tracking=True)
    current_holder_employee_id = fields.Many2one("ab_hr_employee", readonly=True, tracking=True)
    current_holder_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        tracking=True,
        index=True,
    )
    current_holder_display = fields.Char(
        compute="_compute_current_holder_display",
        store=True,
    )
    warehouse_required = fields.Boolean(
        default=lambda self: self._default_warehouse_required(),
        tracking=True,
    )
    available_warehouse_store_ids = fields.Many2many(
        "ab_store",
        compute="_compute_available_warehouse_store_ids",
    )
    warehouse_store_id = fields.Many2one(
        "ab_store",
        string="Warehouse",
        domain=[
            ("active", "=", True),
            ("name", "=ilike", "مخزن%"),
        ],
        default=lambda self: self._default_warehouse_store_id(),
        tracking=True,
    )
    warehouse_received_by_id = fields.Many2one("res.users", readonly=True, index=True)
    warehouse_received_date = fields.Datetime(readonly=True)
    can_current_user_receive_warehouse = fields.Boolean(
        compute="_compute_can_current_user_receive_warehouse",
    )

    line_ids = fields.One2many(
        "ab_internal_shipment.line",
        "shipment_id",
        string="Shipment Contents",
    )
    history_ids = fields.One2many(
        "ab_internal_shipment.history",
        "shipment_id",
        string="Movement History",
        readonly=True,
    )
    delivery_proof_attachment_ids = fields.Many2many(
        "ir.attachment",
        "ab_internal_shipment_delivery_proof_rel",
        "shipment_id",
        "attachment_id",
        string="Delivery Proof",
        help="Signed receipt, delivery image, or confirmation document.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = sequence.next_by_code("ab.internal.shipment") or "/"
            vals.setdefault("created_by_id", self.env.uid)
            vals.update(self._get_current_user_sender_values())
        records = super().create(vals_list)
        records._set_current_holder_from_sender()
        for record in records:
            record._create_history("created", False, record.state, _("Shipment created."))
        return records

    @api.model
    def _get_current_user_sender_values(self):
        user = self.env.user
        branch = user.ab_department_ids.store_id.filtered(lambda store: store.store_type == "branch")[:1]
        if branch:
            return {
                "sender_type": "branch",
                "sender_store_id": branch.id,
                "sender_department_id": False,
                "sender_employee_id": False,
                "sender_employee_selection_type": "all",
                "sender_selected_employee_ids": [(5, 0, 0)],
            }
        return {
            "sender_type": "user",
            "sender_store_id": False,
            "sender_department_id": False,
            "sender_employee_id": False,
            "sender_employee_selection_type": "all",
            "sender_selected_employee_ids": [(5, 0, 0)],
        }

    @api.model
    def _default_warehouse_required(self):
        policy = self.env["ir.config_parameter"].sudo().get_param(
            "ab_internal_shipment_tracking.warehouse_policy",
            "never",
        )
        if policy == "always":
            return True
        if policy == "devices":
            return self.default_get(["shipment_type"]).get("shipment_type") == "devices"
        return False

    @api.model
    def _default_warehouse_store_id(self):
        warehouse_id = self.env["ir.config_parameter"].sudo().get_param(
            "ab_internal_shipment_tracking.default_warehouse_store_id"
        )
        if not warehouse_id or not warehouse_id.isdigit():
            return False
        warehouse = self.env["ab_store"].browse(int(warehouse_id))
        valid_warehouse_ids = set(self._get_valid_warehouse_stores().ids)
        return warehouse.id if warehouse.exists() and warehouse.id in valid_warehouse_ids else False

    @api.model
    def _get_valid_warehouse_stores(self):
        return self.env["ab_store"].search([
            ("active", "=", True),
            ("name", "=ilike", "مخزن%"),
        ])

    def _compute_available_warehouse_store_ids(self):
        stores = self._get_valid_warehouse_stores()
        for record in self:
            record.available_warehouse_store_ids = stores

    def write(self, vals):
        res = super().write(vals)
        party_fields = {
            "sender_type",
            "sender_store_id",
            "sender_department_id",
            "sender_employee_id",
            "warehouse_required",
            "warehouse_store_id",
        }
        draft_records = self.filtered(lambda record: record.state == "draft")
        if draft_records and party_fields.intersection(vals):
            draft_records._set_current_holder_from_sender()
        return res

    @api.onchange("sender_type")
    def _onchange_sender_type(self):
        self.sender_store_id = False
        self.sender_department_id = False
        self.sender_employee_id = False
        self.sender_employee_selection_type = "all"
        self.sender_selected_employee_ids = [(5, 0, 0)]

    @api.onchange("recipient_type")
    def _onchange_recipient_type(self):
        self.recipient_store_id = False
        self.recipient_department_id = False
        self.recipient_employee_id = False
        self.recipient_employee_selection_type = "all"
        self.recipient_selected_employee_ids = [(5, 0, 0)]

    @api.onchange("sender_department_id")
    def _onchange_sender_department_id(self):
        self.sender_employee_selection_type = "all"
        self.sender_selected_employee_ids = [(5, 0, 0)]
        if self.sender_department_id:
            return {
                "domain": {
                    "sender_selected_employee_ids": [
                        ("department_id", "=", self.sender_department_id.id),
                    ],
                },
            }
        return {
            "domain": {
                "sender_selected_employee_ids": [],
            },
        }

    @api.onchange("recipient_department_id")
    def _onchange_recipient_department_id(self):
        self.recipient_employee_selection_type = "all"
        self.recipient_selected_employee_ids = [(5, 0, 0)]
        if self.recipient_department_id:
            return {
                "domain": {
                    "recipient_selected_employee_ids": [
                        ("department_id", "=", self.recipient_department_id.id),
                    ],
                },
            }
        return {
            "domain": {
                "recipient_selected_employee_ids": [],
            },
        }

    @api.onchange("sender_store_id")
    def _onchange_sender_store_id(self):
        self.sender_employee_selection_type = "all"
        self.sender_selected_employee_ids = [(5, 0, 0)]
        if self.sender_store_id:
            return {
                "domain": {
                    "sender_selected_employee_ids": [
                        ("department_id.store_id", "=", self.sender_store_id.id),
                    ],
                },
            }
        return {
            "domain": {
                "sender_selected_employee_ids": [],
            },
        }

    @api.onchange("recipient_store_id")
    def _onchange_recipient_store_id(self):
        self.recipient_employee_selection_type = "all"
        self.recipient_selected_employee_ids = [(5, 0, 0)]
        if self.recipient_store_id:
            return {
                "domain": {
                    "recipient_selected_employee_ids": [
                        ("department_id.store_id", "=", self.recipient_store_id.id),
                    ],
                },
            }
        return {
            "domain": {
                "recipient_selected_employee_ids": [],
            },
        }

    @api.onchange("shipment_type")
    def _onchange_shipment_type(self):
        policy = self.env["ir.config_parameter"].sudo().get_param(
            "ab_internal_shipment_tracking.warehouse_policy",
            "never",
        )
        if policy == "always":
            self.warehouse_required = True
        elif policy == "devices":
            self.warehouse_required = self.shipment_type == "devices"

    @api.constrains(
        "sender_type",
        "sender_store_id",
        "sender_department_id",
        "sender_employee_id",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
        "warehouse_required",
        "warehouse_store_id",
        "line_ids",
    )
    def _check_required_entities(self):
        for record in self:
            record._validate_party("sender")
            record._validate_party("recipient")
            if record.warehouse_required and not record.warehouse_store_id:
                raise ValidationError(_("Select the warehouse for this shipment."))
            if not record.line_ids:
                raise ValidationError(_("Add at least one shipment content line."))

    @api.depends("state", "expected_delivery_date")
    def _compute_is_delayed(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_delayed = (
                bool(record.expected_delivery_date)
                and record.expected_delivery_date < today
                and record.state not in ("received", "closed")
            )

    @api.depends(
        "sender_type",
        "sender_employee_id.user_id",
        "sender_department_id.manager_id.user_id",
        "sender_store_id",
        "created_by_id",
        "recipient_type",
        "recipient_employee_id.user_id",
        "recipient_department_id.manager_id.user_id",
        "recipient_store_id",
    )
    def _compute_party_users(self):
        for record in self:
            record.sender_user_id = record._get_party_user("sender")
            record.recipient_user_id = record._get_party_user("recipient")

    @api.depends(
        "sender_type",
        "sender_store_id",
        "sender_department_id",
        "sender_employee_id",
        "created_by_id",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
    )
    def _compute_party_displays(self):
        for record in self:
            record.sender_display = record._get_party_display("sender")
            record.recipient_display = record._get_party_display("recipient")

    @api.depends("sender_type", "created_by_id")
    def _compute_sender_managed_department_display(self):
        Department = self.env["ab_hr_department"]
        for record in self:
            if not record.created_by_id or record.sender_type == "branch":
                record.sender_managed_department_display = False
                continue
            departments = Department.search([("manager_id.user_id", "=", record.created_by_id.id)])
            record.sender_managed_department_display = ", ".join(departments.mapped("display_name"))

    @api.depends(
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
        "recipient_employee_selection_type",
        "recipient_selected_employee_ids",
    )
    def _compute_recipient_confirmation_employee_ids(self):
        for record in self:
            if (
                record.recipient_type in ("department", "branch")
                and record.recipient_employee_selection_type == "all"
            ):
                record.recipient_confirmation_employee_ids = record._get_party_employees("recipient")
            else:
                record.recipient_confirmation_employee_ids = self.env["ab_hr_employee"]

    @api.depends(
        "sender_type",
        "sender_store_id",
        "sender_department_id",
        "sender_employee_id",
        "sender_employee_selection_type",
        "sender_selected_employee_ids",
        "created_by_id",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
        "recipient_employee_selection_type",
        "recipient_selected_employee_ids",
        "state",
        "warehouse_required",
        "warehouse_store_id",
    )
    def _compute_route_users(self):
        for record in self:
            sender_users = record._get_party_users("sender", include_branch_accounts=True)
            recipient_users = record._get_party_users("recipient", include_branch_accounts=True)
            warehouse_users = record._get_warehouse_users()
            record.sender_route_user_ids = sender_users
            record.recipient_route_user_ids = recipient_users
            record.warehouse_route_user_ids = warehouse_users
            if record.state == "awaiting_warehouse_receipt":
                record.receipt_route_user_ids = warehouse_users
            elif record.state == "awaiting_receipt":
                record.receipt_route_user_ids = recipient_users
            else:
                record.receipt_route_user_ids = self.env["res.users"]

    @api.depends(
        "current_holder_type",
        "current_holder_store_id",
        "current_holder_department_id",
        "current_holder_employee_id",
        "current_holder_user_id",
    )
    def _compute_current_holder_display(self):
        for record in self:
            if record.current_holder_type == "branch":
                record.current_holder_display = record.current_holder_store_id.display_name
            elif record.current_holder_type == "department":
                record.current_holder_display = record.current_holder_department_id.display_name
            elif record.current_holder_type == "employee":
                record.current_holder_display = record.current_holder_employee_id.display_name
            elif record.current_holder_type == "user":
                record.current_holder_display = record.current_holder_user_id.display_name
            else:
                record.current_holder_display = False

    @api.depends("state", "warehouse_route_user_ids")
    @api.depends_context("uid")
    def _compute_can_current_user_receive_warehouse(self):
        user = self.env.user
        has_group = user.has_group(
            "ab_internal_shipment_tracking.group_ab_internal_shipment_warehouse_receipt"
        )
        for record in self:
            record.can_current_user_receive_warehouse = (
                has_group
                and record.state == "awaiting_warehouse_receipt"
                and user in record.warehouse_route_user_ids
            )

    @api.depends(
        "state",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_department_id.manager_id.user_id",
        "recipient_employee_id.user_id",
        "recipient_employee_selection_type",
        "recipient_selected_employee_ids",
    )
    @api.depends_context("uid")
    def _compute_can_current_user_receive(self):
        user = self.env.user
        employee_ids = set(user.ab_employee_ids.ids)
        branch_account_store_ids = set(user.ab_department_ids.store_id.ids)
        for record in self:
            can_receive = False
            if record.state == "awaiting_receipt":
                if record.recipient_type == "employee":
                    can_receive = record.recipient_employee_id.id in employee_ids
                elif record.recipient_type == "department":
                    can_receive = record.recipient_department_id.manager_id.user_id == user
                    if not can_receive:
                        recipient_employees = record._get_party_employees("recipient")
                        can_receive = bool(set(recipient_employees.ids) & employee_ids)
                elif record.recipient_type == "branch":
                    can_receive = record.recipient_store_id.id in branch_account_store_ids
                    if not can_receive:
                        recipient_employees = record._get_party_employees("recipient")
                        can_receive = bool(set(recipient_employees.ids) & employee_ids)
            record.can_current_user_receive = can_receive

    @api.depends("state", "created_by_id")
    @api.depends_context("uid")
    def _compute_current_user_action_permissions(self):
        user = self.env.user
        for record in self:
            record.can_current_user_manage_workflow = record.created_by_id == user
            record.can_current_user_close = record.state == "received"

    def action_send(self):
        self._check_current_user_can_manage_workflow()
        for record in self:
            recipient_users = record._get_party_users("recipient")
            if recipient_users:
                record.message_subscribe(partner_ids=recipient_users.partner_id.ids)
        self._move_state("draft", "sent", "sent_by_id", "sent_date", "sent")

    def action_mark_in_transit(self):
        self._check_current_user_can_manage_workflow()
        self._move_state(("sent",), "in_transit", False, False, "in_transit")

    def action_deliver(self):
        self._check_current_user_can_manage_workflow()
        if not self.env.context.get("skip_delivery_evidence_wizard"):
            self.ensure_one()
            return {
                "type": "ir.actions.act_window",
                "name": _("Capture Delivery Evidence"),
                "res_model": "ab_internal_shipment.delivery_wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_shipment_id": self.id,
                },
            }
        redirect_after_delivery = self._should_redirect_after_branch_delivery()
        for record in self:
            if record.state not in ("sent", "in_transit"):
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to %(target)s.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                        "target": "awaiting_receipt",
                    }
                )
            if record.warehouse_required and not record.warehouse_received_date:
                record._schedule_warehouse_receipt_activity()
                target_state = "awaiting_warehouse_receipt"
            else:
                record._schedule_receipt_activity()
                target_state = "awaiting_receipt"
            record._move_state(
                ("sent", "in_transit"),
                target_state,
                "delivered_by_id",
                "delivered_date",
                "delivered",
            )
        if redirect_after_delivery:
            list_view = self.env.ref("ab_internal_shipment_tracking.ab_internal_shipment_view_list")
            form_view = self.env.ref("ab_internal_shipment_tracking.ab_internal_shipment_view_form")
            return {
                "type": "ir.actions.act_window",
                "name": _("Internal Shipments"),
                "res_model": "ab_internal_shipment",
                "view_mode": "list,form",
                "views": [(list_view.id, "list"), (form_view.id, "form")],
                "search_view_id": self.env.ref(
                    "ab_internal_shipment_tracking.ab_internal_shipment_view_search"
                ).id,
                "context": {
                    "list_view_ref": "ab_internal_shipment_tracking.ab_internal_shipment_view_list",
                    "form_view_ref": "ab_internal_shipment_tracking.ab_internal_shipment_view_form",
                },
            }
        return False

    def action_confirm_warehouse_receipt(self):
        unauthorized = self.filtered(lambda record: not record.can_current_user_receive_warehouse)
        if unauthorized:
            raise UserError(_("Only the warehouse recipient can confirm receipt for this shipment."))
        now = fields.Datetime.now()
        for record in self:
            if record.state != "awaiting_warehouse_receipt":
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to recipient receipt.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                    }
                )
            old_state = record.state
            old_holder = record.current_holder_display
            record.write(
                {
                    "state": "awaiting_receipt",
                    "warehouse_received_by_id": self.env.uid,
                    "warehouse_received_date": now,
                    **record._holder_values_for_state("awaiting_receipt"),
                }
            )
            record._create_history(
                "warehouse_received",
                old_state,
                "awaiting_receipt",
                _("Warehouse receipt confirmed."),
                old_holder=old_holder,
            )
            record._schedule_receipt_activity()

    def action_receive(self):
        unauthorized = self.filtered(lambda record: not record.can_current_user_receive)
        if unauthorized:
            raise UserError(_("Only the designated recipient can confirm receipt for this shipment."))
        now = fields.Datetime.now()
        for record in self:
            if record.state != "awaiting_receipt":
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to received.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                    }
                )
            old_state = record.state
            old_holder = record.current_holder_display
            vals = {
                "state": "received",
                "received_by_id": self.env.uid,
                "received_date": now,
            }
            vals.update(record._holder_values_for_state("received"))
            record.write(vals)
            record._create_history(
                "received",
                old_state,
                "received",
                _("State changed."),
                old_holder=old_holder,
            )

    def action_close(self):
        unauthorized = self.filtered(lambda record: not record.can_current_user_close)
        if unauthorized:
            raise UserError(_("Only confirmed shipments can be closed."))
        now = fields.Datetime.now()
        action_uid = self.env.uid
        for record in self:
            if record.state != "received":
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to closed.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                    }
                )
            old_state = record.state
            old_holder = record.current_holder_display
            vals = {
                "state": "closed",
                "closed_by_id": action_uid,
                "closed_date": now,
            }
            vals.update(record._holder_values_for_state("closed"))
            record.write(vals)
            record.with_context(ab_internal_shipment_action_uid=action_uid)._create_history(
                "closed",
                old_state,
                "closed",
                _("State changed."),
                old_holder=old_holder,
            )

    def action_add_tracking_note(self):
        for record in self:
            record._create_history("note", record.state, record.state, record.notes or _("Tracking note added."))

    def _move_state(self, allowed_from, target_state, user_field, date_field, action):
        allowed = {allowed_from} if isinstance(allowed_from, str) else set(allowed_from)
        now = fields.Datetime.now()
        for record in self:
            if record.state not in allowed:
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to %(target)s.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                        "target": target_state,
                    }
                )
            old_state = record.state
            old_holder = record.current_holder_display
            vals = {"state": target_state}
            if user_field:
                vals[user_field] = self.env.uid
            if date_field:
                vals[date_field] = now
            vals.update(record._holder_values_for_state(target_state))
            record.write(vals)
            record._create_history(action, old_state, target_state, _("State changed."), old_holder=old_holder)

    def _check_current_user_can_manage_workflow(self):
        unauthorized = self.filtered(lambda record: not record.can_current_user_manage_workflow)
        if unauthorized:
            raise UserError(_("Only the shipment creator can perform this action."))

    def _should_redirect_after_branch_delivery(self):
        user = self.env.user
        branch_account_store_ids = set(user.ab_department_ids.store_id.ids)
        return any(
            record.recipient_type == "branch"
            and record.recipient_store_id.id not in branch_account_store_ids
            for record in self
        )

    def _holder_values_for_state(self, state):
        self.ensure_one()
        if state in ("draft", "sent", "in_transit"):
            return self._holder_values_from_party("sender")
        if state == "awaiting_warehouse_receipt":
            return self._holder_values_from_warehouse()
        return self._holder_values_from_party("recipient")

    def _holder_values_from_warehouse(self):
        self.ensure_one()
        return {
            "current_holder_type": "branch",
            "current_holder_store_id": self.warehouse_store_id.id,
            "current_holder_department_id": False,
            "current_holder_employee_id": False,
            "current_holder_user_id": False,
        }

    def _set_current_holder_from_sender(self):
        for record in self:
            record.write(record._holder_values_from_party("sender"))

    def _holder_values_from_party(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        values = {
            "current_holder_type": party_type,
            "current_holder_store_id": False,
            "current_holder_department_id": False,
            "current_holder_employee_id": False,
            "current_holder_user_id": self._get_party_user(party).id,
        }
        if party_type == "branch":
            values["current_holder_store_id"] = self[f"{party}_store_id"].id
        elif party_type == "department":
            values["current_holder_department_id"] = self[f"{party}_department_id"].id
        elif party_type == "employee":
            values["current_holder_employee_id"] = self[f"{party}_employee_id"].id
        elif party_type == "user":
            values["current_holder_type"] = "user"
        return values

    def _get_party_display(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        if party_type == "branch":
            return self[f"{party}_store_id"].display_name
        if party_type == "department":
            return self[f"{party}_department_id"].display_name
        if party_type == "employee":
            return self[f"{party}_employee_id"].display_name
        if party_type == "user":
            return self.created_by_id.display_name
        return False

    def _get_party_user(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        if party_type == "employee":
            return self[f"{party}_employee_id"].user_id
        if party_type == "department":
            return self[f"{party}_department_id"].manager_id.user_id
        if party_type == "user":
            return self.created_by_id
        return self.env["res.users"]

    def _get_party_employees(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        if party_type == "employee":
            return self[f"{party}_employee_id"]
        if party_type == "department":
            dept = self[f"{party}_department_id"]
            if not dept:
                return self.env["ab_hr_employee"]
            if self[f"{party}_employee_selection_type"] == "specific":
                return self[f"{party}_selected_employee_ids"]
            employees = self.env["ab_hr_employee"]
            dept_occupied = dept.occupied_job_ids.mapped("employee_id")
            if dept_occupied:
                employees |= dept_occupied
            direct = self.env["ab_hr_employee"].search([
                ("department_id", "=", dept.id),
            ])
            if direct:
                employees |= direct
            return employees
        if party_type == "branch":
            store = self[f"{party}_store_id"]
            if not store:
                return self.env["ab_hr_employee"]
            if self[f"{party}_employee_selection_type"] == "specific":
                return self[f"{party}_selected_employee_ids"]
            branch_depts = self.env["ab_hr_department"].search([
                ("store_id", "=", store.id),
            ])
            employees = self.env["ab_hr_employee"]
            if branch_depts:
                dept_occupied = branch_depts.mapped("occupied_job_ids").mapped("employee_id")
                if dept_occupied:
                    employees |= dept_occupied
                direct = self.env["ab_hr_employee"].search([
                    ("department_id", "in", branch_depts.ids),
                ])
                if direct:
                    employees |= direct
            return employees
        return self.env["ab_hr_employee"]

    def _get_party_users(self, party, include_branch_accounts=False):
        self.ensure_one()
        employees = self._get_party_employees(party)
        users = employees.mapped("user_id").filtered(lambda u: u)
        if self[f"{party}_type"] == "branch":
            store = self[f"{party}_store_id"]
            if store:
                branch_depts = self.env["ab_hr_department"].search([
                    ("store_id", "=", store.id),
                ])
                if branch_depts:
                    manager_users = branch_depts.mapped("manager_id.user_id").filtered(lambda u: u)
                    users |= manager_users
                    if include_branch_accounts:
                        account_users = self.env["res.users"].search([
                            ("ab_department_ids.store_id", "=", store.id),
                        ])
                        users |= account_users
        return users

    def _get_warehouse_users(self):
        self.ensure_one()
        if not self.warehouse_required or not self.warehouse_store_id:
            return self.env["res.users"]
        if (
            not self.warehouse_store_id.active
            or not (self.warehouse_store_id.name or "").startswith("مخزن")
        ):
            return self.env["res.users"]
        departments = self.env["ab_hr_department"].sudo().search([
            "|",
            ("store_id", "=", self.warehouse_store_id.id),
            ("id", "=", self.warehouse_store_id.id),
        ])
        occupied_jobs = self.env["ab_hr_job_occupied"].sudo().search([
            ("workplace", "in", departments.ids),
            ("job_status", "!=", "inactive"),
        ])
        users = occupied_jobs.mapped("employee_id.user_id").filtered(lambda user: user)
        users |= departments.mapped("manager_id.user_id").filtered(lambda user: user)
        return users.filtered(
            lambda user: user.has_group(
                "ab_internal_shipment_tracking.group_ab_internal_shipment_warehouse_receipt"
            )
        )

    def _validate_party(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        fields_by_type = {
            "branch": f"{party}_store_id",
            "department": f"{party}_department_id",
            "employee": f"{party}_employee_id",
            "user": False,
        }
        required_field = fields_by_type[party_type]
        if required_field and not self[required_field]:
            raise ValidationError(_("Select the %(party)s %(type)s.") % {"party": party, "type": party_type})
        for field_name in fields_by_type.values():
            if field_name and field_name != required_field and self[field_name]:
                raise ValidationError(
                    _("Only the selected %(party)s entity type can be filled.") % {"party": party}
                )

    def _create_history(self, action, state_from, state_to, notes=False, old_holder=False):
        History = self.env["ab_internal_shipment.history"]
        action_uid = self.env.context.get("ab_internal_shipment_action_uid", self.env.uid)
        for record in self:
            History.create(
                {
                    "shipment_id": record.id,
                    "action": action,
                    "action_by_id": action_uid,
                    "action_date": fields.Datetime.now(),
                    "state_to": state_to or "",
                    "state_from": state_from or "",
                    "from_holder_display": old_holder or "",
                    "to_holder_display": record.current_holder_display or "",
                    "notes": notes,
                }
            )

    def _schedule_receipt_activity(self):
        self.ensure_one()
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        recipient_users = self._get_party_users("recipient")
        self._schedule_receipt_activity_for_users(recipient_users, activity_type)

    def _schedule_warehouse_receipt_activity(self):
        self.ensure_one()
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        warehouse_users = self._get_warehouse_users()
        self._schedule_receipt_activity_for_users(warehouse_users, activity_type)

    def _schedule_receipt_activity_for_users(self, users, activity_type):
        self.ensure_one()
        shipment = self.sudo()
        for user in users:
            existing = shipment.activity_ids.filtered(
                lambda a, u=user, at=activity_type: a.activity_type_id == at and a.user_id == u
            )
            if existing:
                continue
            shipment.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=user.id,
                summary=_("Shipment delivered, confirm receipt"),
                note=_("Shipment %s has been delivered and is awaiting receipt confirmation.") % shipment.name,
            )
